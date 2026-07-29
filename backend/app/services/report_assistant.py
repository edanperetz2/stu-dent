from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.models.report import Report, ReportContentSource, ReportPeriodType
from app.models.user import User
from app.services import ollama_client
from app.services.nl_dates import resolve_date_range
from app.services.report_data import resource_utilization, time_impact

_UNSUPPORTED_MESSAGE = (
    "I can currently only answer questions about resource (room/equipment) "
    "utilization or time lost to no-shows and cancellations. Try asking "
    'something like "which equipment is underused this month?" or "which '
    'patient wasted the most of my time this week?"'
)

_ASSISTANT_UNAVAILABLE_MESSAGE = (
    "The report assistant is currently unavailable (the local AI model "
    "couldn't be reached). Try again in a moment."
)

_NARRATE_PROMPT_TEMPLATE = (
    "Write a short, plain-English summary (3-5 sentences) of this "
    "dental-clinic data for a {audience}, as JSON with exactly one key "
    '"summary" (a string). If resource_utilization data is present, name '
    "the single most over-used and most under-used resource. If "
    "time_impact data is present, name the actor with the most lost time. "
    "If a data list is empty, say plainly that there was no notable "
    "activity instead of inventing detail. Use only the numbers given "
    "exactly as they appear -- never invent a figure that isn't in the "
    "data, and never compute a new number (a rate, average, ratio, or any "
    "other derived figure) that isn't already present in the data. "
    "Respond with only the JSON object, no extra text.\n\nData (JSON): {data}"
)

_CLASSIFY_PROMPT_TEMPLATE = (
    "Classify this question about dental-clinic data as JSON with exactly "
    'these keys: "question_type" (one of "resource_utilization", '
    '"time_impact", or "unsupported"), "date_range_phrase" (a short phrase '
    'like "this week", "this month", "last month", or null if not '
    'mentioned). Use "resource_utilization" for questions about how much a '
    "room or piece of equipment is used, over-used, or under-used. Use "
    '"time_impact" for questions about no-shows, cancellations, or time '
    'wasted by a patient, student, or attending. Use "unsupported" for '
    "anything else. Respond with only the JSON object, no extra "
    "text.\n\nQuestion: {question}"
)


class _NarrateResponse(BaseModel):
    summary: str


class _ClassifyResponse(BaseModel):
    question_type: Literal["resource_utilization", "time_impact", "unsupported"]
    date_range_phrase: str | None = None


def _format_resource_utilization_plainly(items: list[dict]) -> list[str]:
    if not items:
        return ["No room or equipment usage recorded in this period."]
    lines = []
    for item in items:
        deviation = item["deviation_from_average"]
        sign = "+" if deviation >= 0 else ""
        lines.append(
            f"{item['resource_name']} ({item['resource_type']}): "
            f"{item['booked_hours']} booked hours across {item['appointment_count']} "
            f"appointments ({sign}{deviation} vs. average)."
        )
    return lines


def _format_time_impact_plainly(items: list[dict]) -> list[str]:
    if not items:
        return ["No no-shows or cancellations recorded in this period."]
    lines = []
    for item in items:
        lines.append(
            f"{item['actor_name']} ({item['actor_type']}): {item['no_show_count']} "
            f"no-shows, {item['cancelled_count']} cancellations, "
            f"{item['minutes_lost']} minutes lost."
        )
    return lines


def _plain_english_fallback(data: dict[str, Any]) -> str:
    """Deterministic, human-readable stand-in for a model summary when
    Ollama is unreachable or returns an unusable response -- formats the
    same already-computed report_data.py numbers as short plain-English
    lines instead of dumping the raw dict/UUID structure at the reader.
    """
    lines: list[str] = []
    if "resource_utilization" in data:
        lines.extend(_format_resource_utilization_plainly(data["resource_utilization"]))
    if "time_impact" in data:
        lines.extend(_format_time_impact_plainly(data["time_impact"]))
    body = "\n".join(f"- {line}" for line in lines)
    return f"AI narration unavailable -- plain summary of the data:\n{body}"


def _narrate(data: dict[str, Any], *, audience: str) -> tuple[str, ReportContentSource]:
    """Returns (content, content_source) -- content_source is `ai` only when
    a real validated model summary was used, `fallback_summary` for the
    deterministic fallback, so callers can record which one actually
    produced the text.
    """
    raw = ollama_client.generate_json(_NARRATE_PROMPT_TEMPLATE.format(audience=audience, data=data))
    try:
        parsed = _NarrateResponse.model_validate(raw) if raw is not None else None
    except ValidationError:
        parsed = None
    if parsed is not None and parsed.summary.strip():
        return parsed.summary, ReportContentSource.ai
    return _plain_english_fallback(data), ReportContentSource.fallback_summary


def generate_periodic_report(
    db: Session,
    recipient: User,
    *,
    period_type: ReportPeriodType,
    period_start: datetime,
    period_end: datetime,
    commit: bool = True,
    resource_utilization_data: list[dict] | None = None,
) -> Report:
    """Compute + narrate a weekly/monthly report for `recipient`. Ollama
    only ever narrates already-computed facts here -- it never sees the DB
    and never contributes a number of its own.

    `resource_utilization_data`, when given, is used as-is instead of being
    recomputed -- it's clinic-wide, not recipient-specific, so a caller
    generating reports for many recipients in the same period (see
    jobs/reports.py) can compute it once and pass it to every recipient
    instead of re-running the same aggregation query per person.

    Commits on its own by default -- every route/job caller treats one
    report as a complete, independent unit of work. `commit=False` lets a
    caller that's managing its own larger transaction (seed_demo.py,
    seeding several reports alongside a lot of other still-uncommitted
    setup) defer that to its own single final commit instead: this used to
    always commit internally, so seed_demo.py's sentinel admin user (and
    everything else built before this ran) was already durably persisted
    the moment the *first* report succeeded -- if a *later* report call
    then failed, a re-run would see the admin already exists and treat
    everything as fully seeded, permanently skipping whatever hadn't
    actually been generated yet.
    """
    data = {
        "resource_utilization": (
            resource_utilization_data
            if resource_utilization_data is not None
            else resource_utilization(db, start=period_start, end=period_end)
        ),
        "time_impact": time_impact(db, scope_user=recipient, start=period_start, end=period_end),
    }
    content, content_source = _narrate(data, audience=f"dental {recipient.role.value}")

    report = Report(
        recipient_id=recipient.id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        question=None,
        title=f"{period_type.value.capitalize()} report "
        f"({period_start.date()} - {period_end.date()})",
        content=content,
        content_source=content_source,
    )
    db.add(report)
    if commit:
        db.commit()
        db.refresh(report)
    else:
        db.flush()
    return report


def answer_ad_hoc_question(db: Session, recipient: User, question: str) -> Report:
    """Classify `question` into a small fixed set of supported types and
    extract a date-range phrase -- the model never sees the database or
    writes a query. Three distinct non-answer outcomes are surfaced
    separately rather than collapsed into one generic message: the
    classify call itself failing entirely (assistant unreachable) vs. it
    succeeding but naming a genuinely unsupported question type vs. the
    narration step itself falling back once a supported type was found.
    """
    raw = ollama_client.generate_json(_CLASSIFY_PROMPT_TEMPLATE.format(question=question))
    try:
        parsed = _ClassifyResponse.model_validate(raw) if raw is not None else None
    except ValidationError:
        parsed = None

    now = datetime.now(UTC)
    date_phrase = parsed.date_range_phrase if parsed is not None else None
    period_start, period_end = resolve_date_range(date_phrase, now=now) or (
        now - timedelta(days=30),
        now,
    )

    if parsed is None:
        content, content_source = _ASSISTANT_UNAVAILABLE_MESSAGE, ReportContentSource.unavailable
    elif parsed.question_type == "resource_utilization":
        data = resource_utilization(db, start=period_start, end=period_end)
        content, content_source = _narrate(
            {"resource_utilization": data}, audience=f"dental {recipient.role.value}"
        )
    elif parsed.question_type == "time_impact":
        data = time_impact(db, scope_user=recipient, start=period_start, end=period_end)
        content, content_source = _narrate(
            {"time_impact": data}, audience=f"dental {recipient.role.value}"
        )
    else:
        content, content_source = _UNSUPPORTED_MESSAGE, ReportContentSource.unsupported

    report = Report(
        recipient_id=recipient.id,
        period_type=ReportPeriodType.ad_hoc,
        period_start=period_start,
        period_end=period_end,
        question=question,
        title=question,
        content=content,
        content_source=content_source,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
