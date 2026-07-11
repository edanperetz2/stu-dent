from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models.student_availability import StudentAvailability
from app.models.user import RoleEnum, User
from app.schemas.availability import AvailabilityWindowIn, AvailabilityWindowOut
from app.services.audit import record_audit_log

router = APIRouter(tags=["availability"])


@router.get("/students/me/availability", response_model=list[AvailabilityWindowOut])
def get_my_availability(
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> list[StudentAvailability]:
    return list(
        db.scalars(
            select(StudentAvailability).where(StudentAvailability.student_id == current_user.id)
        )
    )


@router.put("/students/me/availability", response_model=list[AvailabilityWindowOut])
def replace_my_availability(
    payload: list[AvailabilityWindowIn],
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> list[StudentAvailability]:
    for window in payload:
        if window.end_time <= window.start_time:
            raise HTTPException(status_code=422, detail="end_time must be after start_time")

    db.execute(delete(StudentAvailability).where(StudentAvailability.student_id == current_user.id))

    windows = [
        StudentAvailability(
            student_id=current_user.id,
            day_of_week=window.day_of_week,
            start_time=window.start_time,
            end_time=window.end_time,
        )
        for window in payload
    ]
    db.add_all(windows)
    db.flush()

    record_audit_log(
        db,
        action="availability_replace",
        actor_id=current_user.id,
        target_type="student_availability",
        target_id=current_user.id,
        extra_data={"window_count": len(windows)},
    )
    db.commit()
    for window in windows:
        db.refresh(window)
    return windows
