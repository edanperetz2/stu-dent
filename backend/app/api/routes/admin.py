import uuid

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


@router.get("/admin/users", response_model=list[UserOut])
def list_users(
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User)))


@router.patch("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role is not None:
        user.role = payload.role

    record_audit_log(
        db,
        action="admin_user_update",
        actor_user_id=current_user.id,
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    db.refresh(user)
    return user


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
