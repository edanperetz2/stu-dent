from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import RoleEnum, User
from app.schemas.user import UserOut

router = APIRouter(tags=["attending"])


@router.get("/attending/dashboard")
def attending_dashboard(
    current_user: User = Depends(require_role(RoleEnum.attending)),
) -> dict[str, str]:
    return {"message": f"Welcome, {current_user.full_name}"}


@router.get("/attendings", response_model=list[UserOut])
def list_attendings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    """Active-only picker list, mirroring GET /rooms and GET /equipment.

    Needed so a student can pick an attending when creating/editing an
    appointment -- there was previously no way for a non-admin to see who
    the attendings even are (GET /admin/users is admin-only).
    """
    return list(
        db.scalars(
            select(User).where(
                User.role == RoleEnum.attending,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
    )
