import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.room import Room
from app.models.user import RoleEnum, User
from app.schemas.room import RoomCreate, RoomOut, RoomUpdate
from app.services.audit import record_audit_log

router = APIRouter(tags=["rooms"])


def _get_room(db: Session, room_id: uuid.UUID) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


@router.post("/admin/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: RoomCreate,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> Room:
    existing = db.scalar(select(Room).where(Room.name == payload.name))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Room name already in use")

    room = Room(name=payload.name)
    db.add(room)
    db.flush()

    record_audit_log(
        db,
        action="room_create",
        actor_user_id=current_user.id,
        target_type="room",
        target_id=room.id,
    )
    db.commit()
    db.refresh(room)
    return room


@router.get("/admin/rooms", response_model=list[RoomOut])
def list_all_rooms(
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> list[Room]:
    return list(db.scalars(select(Room)))


@router.patch("/admin/rooms/{room_id}", response_model=RoomOut)
def update_room(
    room_id: uuid.UUID,
    payload: RoomUpdate,
    current_user: User = Depends(require_role(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> Room:
    room = _get_room(db, room_id)

    if payload.name is not None:
        room.name = payload.name
    if payload.is_active is not None:
        room.is_active = payload.is_active

    record_audit_log(
        db,
        action="room_update",
        actor_user_id=current_user.id,
        target_type="room",
        target_id=room.id,
    )
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms", response_model=list[RoomOut])
def list_active_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Room]:
    return list(db.scalars(select(Room).where(Room.is_active.is_(True))))
