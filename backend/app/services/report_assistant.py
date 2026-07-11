from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.report import Report, ReportPeriodType
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

_NARRATE_PROMPT_TEMPLATE = (
    "Write a short, plain-English summary (3-5 sentences) of this "
    "dental-clinic data for a {audience}, as JSON with exactly one key "
    '"summary" (a string). Use only the numbers given -- never invent a '
    "figure that isn't in the data.\n\nData (JSON): {data}"
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
    "anything else.\n\nQuestion: {question}"
)


def _narrate(data: dict[str, Any], *, audience: str) -> str:
    raw = ollama_client.generate_json(_NARRATE_PROMPT_TEMPLATE.format(audience=audience, data=data))
    if raw is not None and isinstance(raw.get("summary"), str):
        return raw["summary"]
    return f"(Narration unavailable -- showing raw data instead)\n{data}"


def generate_periodic_report(
    db: Session,
    recipient: User,
    *,
    period_type: ReportPeriodType,
    period_start: datetime,
    period_end: datetime,
) -> Report:
    """Compute + narrate a weekly/monthly report for `recipient`. Ollama
    only ever narrates already-computed facts here -- it never sees the DB
    and never contributes a number of its own.
    """
    data = {
        "resource_utilization": resource_utilization(db, start=period_start, end=period_end),
        "time_impact": time_impact(db, scope_user=recipient, start=period_start, end=period_end),
    }
    content = _narrate(data, audience=f"dental {recipient.role.value}")

    report = Report(
        recipient_id=recipient.id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        question=None,
        title=f"{period_type.value.capitalize()} report "
        f"({period_start.date()} - {period_end.date()})",
        content=content,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def answer_ad_hoc_question(db: Session, recipient: User, question: str) -> Report:
    """Classify `question` into a small fixed set of supported types and
    extract a date-range phrase -- the model never sees the database or
    writes a query. If the question doesn't match a supported type (or the
    model call fails), a plain "unsupported" report is saved and returned
    rather than guessing an answer.
    """
    raw = ollama_client.generate_json(_CLASSIFY_PROMPT_TEMPLATE.format(question=question))

    now = datetime.now(UTC)
    question_type = raw.get("question_type") if raw else None
    date_phrase = raw.get("date_range_phrase") if raw else None
    period_start, period_end = resolve_date_range(date_phrase, now=now) or (
        now - timedelta(days=30),
        now,
    )

    if question_type == "resource_utilization":
        data = resource_utilization(db, start=period_start, end=period_end)
        content = _narrate(
            {"resource_utilization": data}, audience=f"dental {recipient.role.value}"
        )
    elif question_type == "time_impact":
        data = time_impact(db, scope_user=recipient, start=period_start, end=period_end)
        content = _narrate({"time_impact": data}, audience=f"dental {recipient.role.value}")
    else:
        content = _UNSUPPORTED_MESSAGE

    report = Report(
        recipient_id=recipient.id,
        period_type=ReportPeriodType.ad_hoc,
        period_start=period_start,
        period_end=period_end,
        question=question,
        title=question,
        content=content,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
