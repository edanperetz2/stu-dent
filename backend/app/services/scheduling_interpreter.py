import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment import Equipment
from app.models.room import Room
from app.models.user import RoleEnum, User
from app.schemas.scheduling_assistant import InterpretedAppointmentOut
from app.services import ollama_client
from app.services.formatting import DISPLAY_TIMEZONE
from app.services.nl_dates import TIME_OF_DAY_HOURS, resolve_relative_date
from app.services.users import active_user_filters

DEFAULT_APPOINTMENT_MINUTES = 30

_PROMPT_TEMPLATE = (
    "Extract scheduling details from this appointment request as JSON with "
    'exactly these keys: "patient_name", "attending_name", "room_name", '
    '"equipment_name", "date_phrase", "time_of_day", "notes". Use null for '
    "any field not mentioned. date_phrase must be a short relative phrase "
    '(e.g. "tomorrow", "next monday", "friday") or null. time_of_day must '
    'be one of "morning", "afternoon", "evening", or null. Do not invent '
    "names or dates that are not in the request.\n\nRequest: {text}"
)


def _as_str(value: object) -> str | None:
    """The model is asked for JSON with specific keys, but nothing enforces
    it actually returns strings for them -- a list/int/bool for a field
    that's supposed to be a name or phrase would otherwise reach `.strip()`
    (AttributeError) or a dict `.get()` key lookup (TypeError: unhashable
    type) below. Treated the same as "field not mentioned" rather than a
    crash.
    """
    return value if isinstance(value, str) else None


def _resolve_by_name(
    candidates: list[tuple[uuid.UUID, str]], name: str | None, label: str
) -> tuple[uuid.UUID | None, list[str]]:
    if not name:
        return None, []
    matches = [c for c in candidates if name.strip().lower() in c[1].lower()]
    if len(matches) == 1:
        return matches[0][0], []
    if not matches:
        return None, [f'Couldn\'t find a {label} matching "{name}" -- pick one manually.']
    return None, [f'Multiple {label}s match "{name}" -- pick one manually.']


def interpret_request(db: Session, *, user: User, text: str) -> InterpretedAppointmentOut:
    """Turn a free-text scheduling request into pre-filled appointment
    fields for the caller to review and submit through the existing
    create-appointment form/endpoint.

    The model only ever supplies candidate *names* and a date/time *phrase*;
    every ID and every date is resolved here deterministically against real
    active rows and server time, never trusted verbatim from the model. Any
    field that can't be confidently resolved is left blank with a warning
    rather than guessed -- this function never creates or books anything.
    """
    raw = ollama_client.generate_json(_PROMPT_TEMPLATE.format(text=text))
    if raw is None:
        return InterpretedAppointmentOut(
            warnings=[
                "The scheduling assistant is unavailable right now -- fill in the fields manually."
            ]
        )

    warnings: list[str] = []
    patient_id: uuid.UUID | None = None
    attending_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None

    # Patients never get attending/room/equipment resolved (left None, no
    # warning) -- mirrors the 422 rule in appointments.py::create_appointment
    # that patients cannot set those fields when requesting an appointment.
    if user.role == RoleEnum.student:
        patients = list(
            db.execute(
                select(User.id, User.full_name).where(
                    User.role == RoleEnum.patient,
                    User.owner_student_id == user.id,
                    User.deleted_at.is_(None),
                )
            )
        )
        attendings = list(
            db.execute(
                select(User.id, User.full_name).where(*active_user_filters(RoleEnum.attending))
            )
        )
        rooms = list(db.execute(select(Room.id, Room.name).where(Room.is_active.is_(True))))
        equipment = list(
            db.execute(select(Equipment.id, Equipment.name).where(Equipment.is_active.is_(True)))
        )

        patient_id, w = _resolve_by_name(patients, _as_str(raw.get("patient_name")), "patient")
        warnings += w
        attending_id, w = _resolve_by_name(
            attendings, _as_str(raw.get("attending_name")), "attending"
        )
        warnings += w
        room_id, w = _resolve_by_name(rooms, _as_str(raw.get("room_name")), "room")
        warnings += w
        equipment_id, w = _resolve_by_name(
            equipment, _as_str(raw.get("equipment_name")), "equipment item"
        )
        warnings += w

    start_time: datetime | None = None
    end_time: datetime | None = None
    date_phrase = _as_str(raw.get("date_phrase"))
    if date_phrase:
        now = datetime.now(UTC)
        resolved_date = resolve_relative_date(date_phrase, now=now)
        if resolved_date is None:
            warnings.append(f'Couldn\'t understand the date "{date_phrase}" -- pick one manually.')
        else:
            time_of_day = _as_str(raw.get("time_of_day"))
            hour = TIME_OF_DAY_HOURS.get(time_of_day, TIME_OF_DAY_HOURS["morning"])
            # tzinfo=DISPLAY_TIMEZONE (not UTC): `hour` is a local Israel
            # wall-clock hour ("afternoon" -> 13:00 local), so it must be
            # tagged with the zone it was meant in, not stamped UTC -- the
            # same instant-vs-wall-clock distinction format_dt exists for.
            start_time = datetime.combine(resolved_date, time(hour=hour), tzinfo=DISPLAY_TIMEZONE)
            end_time = start_time + timedelta(minutes=DEFAULT_APPOINTMENT_MINUTES)

    notes = _as_str(raw.get("notes"))

    return InterpretedAppointmentOut(
        patient_id=patient_id,
        attending_id=attending_id,
        room_id=room_id,
        equipment_id=equipment_id,
        start_time=start_time,
        end_time=end_time,
        notes=notes,
        warnings=warnings,
    )
