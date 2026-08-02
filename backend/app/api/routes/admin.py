import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import RoleEnum, User
from app.schemas.admin import AdminUserUpdate, AuditLogOut
from app.schemas.user import UserOut
from app.services.audit import record_audit_log

router = APIRouter(tags=["admin"])


def _get_active_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/admin/users", response_model=list[UserOut])
def list_users(
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> list[User]:
    # Defensive cap, not full pagination (out of scope for this fix) --
    # nothing on this table is ever hard-deleted, so it grows monotonically
    # for the life of the app; this just guarantees the response can never
    # be truly unbounded.
    stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc()).limit(500)
    return list(db.scalars(stmt))


@router.get("/admin/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> User:
    return _get_active_user(db, user_id)


@router.patch("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> User:
    user = _get_active_user(db, user_id)

    if user_id == current_user.id:
        if payload.role is not None and payload.role != RoleEnum.admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role"
            )
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account",
            )

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role is not None:
        # patient has its own dedicated creation/confirmation flows
        # (POST /patients, self-registration + POST /patients/{id}/confirm)
        # that populate owner_student_id/owner_confirmed_at -- an admin
        # role-flip was never meant to reach this. Flipping a student *to*
        # patient leaves those columns NULL (a permanent 403 dead-end via
        # require_confirmed_patient) and orphans any patients/appointments
        # that referenced them in their old role; flipping a patient *away*
        # would silently strand the columns the other way.
        if payload.role == RoleEnum.patient or user.role == RoleEnum.patient:
            raise HTTPException(
                status_code=422,
                detail="Cannot change a user's role into or out of patient via this endpoint",
            )
        user.role = payload.role

    record_audit_log(
        db,
        action="admin_user_update",
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> None:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account"
        )

    user = _get_active_user(db, user_id)
    user.deleted_at = datetime.now(UTC)
    user.is_active = False

    record_audit_log(
        db,
        action="admin_user_delete",
        actor_id=current_user.id,
        target_type="user",
        target_id=user.id,
    )
    db.commit()


@router.get("/admin/audit-log", response_model=list[AuditLogOut])
def list_audit_log(
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLog]:
    return list(
        db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit))
    )
