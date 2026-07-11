import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.core.security import PrincipalType
from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import RoleEnum
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.services.audit import record_audit_log
from app.services.scheduling import (
    TERMINAL_STATUSES,
    flush_or_409,
    recompute_status,
    validate_participants,
)
from app.services.waitlist import check_and_notify_waitlist

router = APIRouter(tags=["appointments"])


def _is_visible(appointment: Appointment, principal: Principal) -> bool:
    if principal.kind == PrincipalType.patient:
        return appointment.patient_id == principal.patient.id

    user = principal.user
    if user.role == RoleEnum.admin:
        return True
    if user.role == RoleEnum.student:
        return appointment.student_id == user.id
    if user.role == RoleEnum.attending:
        return appointment.attending_id == user.id
    return False


def _get_visible_appointment(
    db: Session, appointment_id: uuid.UUID, principal: Principal
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or not _is_visible(appointment, principal):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


def _require_owning_student(appointment: Appointment, principal: Principal) -> None:
    if (
        principal.kind != PrincipalType.user
        or principal.user.role != RoleEnum.student
        or appointment.student_id != principal.user.id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owning student")


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    if principal.kind == PrincipalType.patient:
        if payload.attending_id or payload.room_id or payload.equipment_id:
            raise HTTPException(
                status_code=422,
                detail="Patients cannot set attending, room, or equipment when requesting",
            )
        student_id = principal.patient.owner_student_id
        patient_id = principal.patient.id
        student_confirmed_at = None
    else:
        if principal.user.role != RoleEnum.student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students or patients can request appointments",
            )
        if payload.patient_id is None:
            raise HTTPException(status_code=422, detail="patient_id is required")
        student_id = principal.user.id
        patient_id = payload.patient_id
        student_confirmed_at = datetime.now(UTC)

    validate_participants(
        db,
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
    )

    appointment = Appointment(
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        notes=payload.notes,
        student_confirmed_at=student_confirmed_at,
    )
    recompute_status(appointment)
    db.add(appointment)
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_create",
        actor_user_id=principal.actor_user_id,
        actor_patient_id=principal.actor_patient_id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[Appointment]:
    stmt = select(Appointment)
    if principal.kind == PrincipalType.patient:
        stmt = stmt.where(Appointment.patient_id == principal.patient.id)
    elif principal.user.role == RoleEnum.student:
        stmt = stmt.where(Appointment.student_id == principal.user.id)
    elif principal.user.role == RoleEnum.attending:
        stmt = stmt.where(Appointment.attending_id == principal.user.id)
    return list(db.scalars(stmt))


@router.get("/appointments/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    return _get_visible_appointment(db, appointment_id, principal)


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, principal)
    _require_owning_student(appointment, principal)

    if appointment.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Cannot edit a finalized appointment")

    fields = payload.model_dump(exclude_unset=True)

    new_start = fields.get("start_time", appointment.start_time)
    new_end = fields.get("end_time", appointment.end_time)
    if new_end <= new_start:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    time_changed = "start_time" in fields or "end_time" in fields
    attending_changed = (
        "attending_id" in fields and fields["attending_id"] != appointment.attending_id
    )

    if "start_time" in fields:
        appointment.start_time = fields["start_time"]
    if "end_time" in fields:
        appointment.end_time = fields["end_time"]
    if "room_id" in fields:
        appointment.room_id = fields["room_id"]
    if "equipment_id" in fields:
        appointment.equipment_id = fields["equipment_id"]
    if "attending_id" in fields:
        appointment.attending_id = fields["attending_id"]
    if "notes" in fields:
        appointment.notes = fields["notes"]

    validate_participants(
        db,
        student_id=appointment.student_id,
        patient_id=appointment.patient_id,
        attending_id=appointment.attending_id,
        room_id=appointment.room_id,
        equipment_id=appointment.equipment_id,
    )

    if time_changed or attending_changed:
        if appointment.attending_id is not None:
            appointment.attending_approved_at = None
        recompute_status(appointment, time_changed=time_changed)

    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_update",
        actor_user_id=principal.actor_user_id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/accept", response_model=AppointmentOut)
def accept_appointment(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, principal)
    _require_owning_student(appointment, principal)

    if appointment.status != AppointmentStatus.proposed:
        raise HTTPException(status_code=409, detail="Only a proposed appointment can be accepted")

    appointment.student_confirmed_at = datetime.now(UTC)
    recompute_status(appointment)
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_accept",
        actor_user_id=principal.actor_user_id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/approve", response_model=AppointmentOut)
def approve_appointment(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, principal)
    if (
        principal.kind != PrincipalType.user
        or principal.user.role != RoleEnum.attending
        or appointment.attending_id != principal.user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not the assigned attending"
        )

    if appointment.status not in (
        AppointmentStatus.awaiting_confirmation,
        AppointmentStatus.rescheduling_requested,
    ):
        raise HTTPException(
            status_code=409, detail="Appointment is not awaiting attending approval"
        )

    appointment.attending_approved_at = datetime.now(UTC)
    recompute_status(appointment)
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_approve",
        actor_user_id=principal.actor_user_id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/reject", response_model=AppointmentOut)
def reject_appointment(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, principal)

    is_owning_student = (
        principal.kind == PrincipalType.user
        and principal.user.role == RoleEnum.student
        and appointment.student_id == principal.user.id
    )
    is_assigned_attending = (
        principal.kind == PrincipalType.user
        and principal.user.role == RoleEnum.attending
        and appointment.attending_id == principal.user.id
    )
    if not (is_owning_student or is_assigned_attending):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reject this appointment",
        )

    if appointment.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Appointment is already finalized")

    appointment.status = AppointmentStatus.cancelled
    check_and_notify_waitlist(db, appointment)
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_reject",
        actor_user_id=principal.actor_user_id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, principal)

    is_owning_student = (
        principal.kind == PrincipalType.user
        and principal.user.role == RoleEnum.student
        and appointment.student_id == principal.user.id
    )
    is_self_patient = (
        principal.kind == PrincipalType.patient and appointment.patient_id == principal.patient.id
    )
    if not (is_owning_student or is_self_patient):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this appointment",
        )

    if appointment.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Appointment is already finalized")

    appointment.status = AppointmentStatus.cancelled
    check_and_notify_waitlist(db, appointment)
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_cancel",
        actor_user_id=principal.actor_user_id,
        actor_patient_id=principal.actor_patient_id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/complete", response_model=AppointmentOut)
def complete_appointment(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, principal)
    _require_owning_student(appointment, principal)

    if appointment.status != AppointmentStatus.confirmed:
        raise HTTPException(status_code=409, detail="Only a confirmed appointment can be completed")

    appointment.status = AppointmentStatus.completed
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_complete",
        actor_user_id=principal.actor_user_id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/no-show", response_model=AppointmentOut)
def mark_no_show(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, principal)
    _require_owning_student(appointment, principal)

    if appointment.status != AppointmentStatus.confirmed:
        raise HTTPException(
            status_code=409, detail="Only a confirmed appointment can be marked no-show"
        )

    appointment.status = AppointmentStatus.no_show
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_no_show",
        actor_user_id=principal.actor_user_id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment
