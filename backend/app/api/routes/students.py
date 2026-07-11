from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import RoleEnum, User
from app.schemas.student import StudentPublicOut

router = APIRouter(tags=["students"])


@router.get("/students", response_model=list[StudentPublicOut])
def list_students(db: Session = Depends(get_db)) -> list[User]:
    """Public, unauthenticated picker list for the registration-time
    "choose your student" dropdown -- registration happens before any
    token exists, so this can't sit behind get_current_user like
    GET /attendings does. Mirrors that endpoint's shape otherwise.
    """
    return list(
        db.scalars(
            select(User).where(
                User.role == RoleEnum.student,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
    )
