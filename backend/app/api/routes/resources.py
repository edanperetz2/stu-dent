from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.appointment import ACTIVE_STATUSES, Appointment
from app.models.user import RoleEnum, User
from app.schemas.resource_schedule import ResourceBookingOut

router = APIRouter(tags=["resources"])


@router.get("/resources/schedule", response_model=list[ResourceBookingOut])
def get_resources_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ResourceBookingOut]:
    """Combined room+equipment busy windows across every user's bookings --
    lets students/attendings/admin see the whole clinic's resource usage and
    coordinate with whichever student booked a slot, without ever exposing
    the patient or any other appointment detail. A patient gets only their
    own bookings -- the clinic-wide feed would otherwise let them learn
    their own treating student is busy elsewhere with a *different*
    patient's care, the same leak `redact_conflicts_for_patient` exists to
    prevent for the waitlist/conflict responses.
    """
    stmt = select(Appointment).where(
        or_(Appointment.room_id.is_not(None), Appointment.equipment_id.is_not(None)),
        Appointment.status.in_(ACTIVE_STATUSES),
    )
    if current_user.role == RoleEnum.patient:
        stmt = stmt.where(Appointment.patient_id == current_user.id)
    appointments = db.scalars(stmt)

    bookings: list[ResourceBookingOut] = []
    for appointment in appointments:
        if appointment.room_id is not None:
            bookings.append(
                ResourceBookingOut(
                    resource_kind="room",
                    resource_id=appointment.room_id,
                    resource_name=appointment.room_name,
                    start_time=appointment.start_time,
                    end_time=appointment.end_time,
                    student_name=appointment.student_name,
                )
            )
        if appointment.equipment_id is not None:
            bookings.append(
                ResourceBookingOut(
                    resource_kind="equipment",
                    resource_id=appointment.equipment_id,
                    resource_name=appointment.equipment_name,
                    start_time=appointment.start_time,
                    end_time=appointment.end_time,
                    student_name=appointment.student_name,
                )
            )
    return bookings
