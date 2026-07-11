import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.equipment import Equipment
from app.models.room import Room
from app.models.user import RoleEnum, User

# Statuses that represent real, non-cancelled use of a resource's time --
# mirrors the "active" set appointments.py's exclusion constraints use, plus
# completed/no_show (a completed or no-show slot still consumed the
# resource's time even though it's no longer an active hold).
_UTILIZED_STATUSES = (
    AppointmentStatus.awaiting_confirmation,
    AppointmentStatus.confirmed,
    AppointmentStatus.rescheduling_requested,
    AppointmentStatus.completed,
    AppointmentStatus.no_show,
)

_LOST_TIME_STATUSES = (AppointmentStatus.cancelled, AppointmentStatus.no_show)


def _booked_hours(appointments: list[Appointment]) -> float:
    total_seconds = sum((a.end_time - a.start_time).total_seconds() for a in appointments)
    return round(total_seconds / 3600, 2)


def resource_utilization(db: Session, *, start: datetime, end: datetime) -> list[dict]:
    """Booked hours + appointment count per active room and equipment item
    in [start, end), plus each resource's deviation from the mean of its
    own category -- a plain average comparison, not ML, so an "over/under
    used" flag stays fully explainable. Shared by the periodic report and
    the ad-hoc "which resource is over/under used" question.
    """
    appointments = list(
        db.scalars(
            select(Appointment).where(
                Appointment.status.in_(_UTILIZED_STATUSES),
                Appointment.start_time >= start,
                Appointment.start_time < end,
            )
        )
    )

    results: list[dict] = []
    for model, id_field, label in (
        (Room, "room_id", "room"),
        (Equipment, "equipment_id", "equipment"),
    ):
        resources = list(db.scalars(select(model).where(model.is_active.is_(True))))
        hours_by_id: dict[uuid.UUID, float] = {}
        count_by_id: dict[uuid.UUID, int] = {}
        for resource in resources:
            matching = [a for a in appointments if getattr(a, id_field) == resource.id]
            hours_by_id[resource.id] = _booked_hours(matching)
            count_by_id[resource.id] = len(matching)

        mean_hours = sum(hours_by_id.values()) / len(resources) if resources else 0.0
        for resource in resources:
            hours = hours_by_id[resource.id]
            results.append(
                {
                    "resource_type": label,
                    "resource_id": str(resource.id),
                    "resource_name": resource.name,
                    "appointment_count": count_by_id[resource.id],
                    "booked_hours": hours,
                    "average_booked_hours_for_type": round(mean_hours, 2),
                    "deviation_from_average": round(hours - mean_hours, 2),
                }
            )

    return results


def time_impact(db: Session, *, scope_user: User, start: datetime, end: datetime) -> list[dict]:
    """No-show/cancelled appointment counts and total lost minutes in
    [start, end), grouped by patient and by the other party (attending for
    a student's own appointments, student for an attending's own
    appointments) -- always scoped to `scope_user`'s own appointments only.
    This scoping is what keeps one user from ever seeing another's data, by
    construction, regardless of what the model does.
    """
    stmt = select(Appointment).where(
        Appointment.status.in_(_LOST_TIME_STATUSES),
        Appointment.start_time >= start,
        Appointment.start_time < end,
    )
    if scope_user.role == RoleEnum.student:
        stmt = stmt.where(Appointment.student_id == scope_user.id)
    elif scope_user.role == RoleEnum.attending:
        stmt = stmt.where(Appointment.attending_id == scope_user.id)
    else:
        return []

    appointments = list(db.scalars(stmt))

    tallies: dict[tuple[str, uuid.UUID], dict] = {}
    for appointment in appointments:
        minutes_lost = (appointment.end_time - appointment.start_time).total_seconds() / 60

        actors: list[tuple[str, uuid.UUID]] = [("patient", appointment.patient_id)]
        if scope_user.role == RoleEnum.student and appointment.attending_id is not None:
            actors.append(("attending", appointment.attending_id))
        elif scope_user.role == RoleEnum.attending:
            actors.append(("student", appointment.student_id))

        for actor_type, actor_id in actors:
            tally = tallies.setdefault(
                (actor_type, actor_id),
                {
                    "actor_type": actor_type,
                    "actor_id": actor_id,
                    "no_show_count": 0,
                    "cancelled_count": 0,
                    "minutes_lost": 0.0,
                },
            )
            if appointment.status == AppointmentStatus.no_show:
                tally["no_show_count"] += 1
            else:
                tally["cancelled_count"] += 1
            tally["minutes_lost"] += minutes_lost

    actor_ids = {actor_id for (_actor_type, actor_id) in tallies}
    names = (
        {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(actor_ids)))}
        if actor_ids
        else {}
    )

    results = [
        {
            "actor_type": actor_type,
            "actor_id": str(actor_id),
            "actor_name": names.get(actor_id, "Unknown"),
            "no_show_count": tally["no_show_count"],
            "cancelled_count": tally["cancelled_count"],
            "minutes_lost": round(tally["minutes_lost"], 1),
        }
        for (actor_type, actor_id), tally in tallies.items()
    ]
    results.sort(key=lambda r: r["minutes_lost"], reverse=True)
    return results
