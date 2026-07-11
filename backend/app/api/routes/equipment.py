import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db, get_or_404
from app.models.equipment import Equipment
from app.models.user import RoleEnum, User
from app.schemas.equipment import EquipmentCreate, EquipmentOut, EquipmentUpdate
from app.services.audit import record_audit_log

router = APIRouter(tags=["equipment"])


@router.post("/admin/equipment", response_model=EquipmentOut, status_code=status.HTTP_201_CREATED)
def create_equipment(
    payload: EquipmentCreate,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> Equipment:
    equipment = Equipment(name=payload.name, equipment_type=payload.equipment_type)
    db.add(equipment)
    db.flush()

    record_audit_log(
        db,
        action="equipment_create",
        actor_id=current_user.id,
        target_type="equipment",
        target_id=equipment.id,
    )
    db.commit()
    db.refresh(equipment)
    return equipment


@router.get("/admin/equipment", response_model=list[EquipmentOut])
def list_all_equipment(
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> list[Equipment]:
    return list(db.scalars(select(Equipment)))


@router.patch("/admin/equipment/{equipment_id}", response_model=EquipmentOut)
def update_equipment(
    equipment_id: uuid.UUID,
    payload: EquipmentUpdate,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> Equipment:
    equipment = get_or_404(db, Equipment, equipment_id, detail="Equipment not found")

    if payload.name is not None:
        equipment.name = payload.name
    if payload.equipment_type is not None:
        equipment.equipment_type = payload.equipment_type
    if payload.is_active is not None:
        equipment.is_active = payload.is_active

    record_audit_log(
        db,
        action="equipment_update",
        actor_id=current_user.id,
        target_type="equipment",
        target_id=equipment.id,
    )
    db.commit()
    db.refresh(equipment)
    return equipment


@router.get("/equipment", response_model=list[EquipmentOut])
def list_active_equipment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Equipment]:
    return list(db.scalars(select(Equipment).where(Equipment.is_active.is_(True))))
