import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.appointment import Appointment
from app.models.feedback import Feedback
from app.models.user import RoleEnum, User
from app.schemas.feedback import FeedbackCreate, FeedbackOut, PendingFeedbackOut
from app.services.audit import record_audit_log
from app.services.feedback import (
    authorize_feedback_author,
    list_feedback_given,
    list_feedback_received,
    list_pending_feedback,
)
from app.services.scheduling import is_visible_to_participant

router = APIRouter(tags=["feedback"])


def _feedback_out(feedback: Feedback) -> FeedbackOut:
    return FeedbackOut(
        id=feedback.id,
        appointment_id=feedback.appointment_id,
        student_id=feedback.student_id,
        author_id=feedback.author_id,
        author_role=feedback.author_role,
        went_well=feedback.went_well,
        could_improve=feedback.could_improve,
        additional_comments=feedback.additional_comments,
        created_at=feedback.created_at,
        student_name=feedback.student_name,
        author_name=feedback.author_name,
        patient_id=feedback.patient_id,
        patient_name=feedback.patient_name,
        appointment_start_time=feedback.appointment_start_time,
    )


def _pending_out(appointment: Appointment) -> PendingFeedbackOut:
    return PendingFeedbackOut(
        appointment_id=appointment.id,
        appointment_start_time=appointment.start_time,
        student_id=appointment.student_id,
        student_name=appointment.student_name,
        patient_id=appointment.patient_id,
        patient_name=appointment.patient_name,
    )


@router.post(
    "/appointments/{appointment_id}/feedback",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
def create_feedback(
    appointment_id: uuid.UUID,
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackOut:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or not is_visible_to_participant(appointment, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    author_role = authorize_feedback_author(appointment, current_user)

    feedback = Feedback(
        appointment_id=appointment.id,
        student_id=appointment.student_id,
        author_id=current_user.id,
        author_role=author_role,
        went_well=payload.went_well,
        could_improve=payload.could_improve,
        additional_comments=payload.additional_comments,
    )
    db.add(feedback)
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You've already given feedback for this appointment",
        ) from err

    record_audit_log(
        db,
        action="feedback_create",
        actor_id=current_user.id,
        target_type="feedback",
        target_id=feedback.id,
    )
    db.commit()
    db.refresh(feedback)
    return _feedback_out(feedback)


@router.get("/feedback/pending", response_model=list[PendingFeedbackOut])
def get_pending_feedback(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PendingFeedbackOut]:
    if current_user.role not in (RoleEnum.patient, RoleEnum.attending):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a patient or attending can have pending feedback",
        )
    return [_pending_out(a) for a in list_pending_feedback(db, current_user)]


@router.get("/feedback/given", response_model=list[FeedbackOut])
def get_feedback_given(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedbackOut]:
    if current_user.role not in (RoleEnum.patient, RoleEnum.attending):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a patient or attending gives feedback",
        )
    return [_feedback_out(f) for f in list_feedback_given(db, current_user.id)]


@router.get("/feedback/received", response_model=list[FeedbackOut])
def get_feedback_received(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedbackOut]:
    if current_user.role != RoleEnum.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a student receives feedback",
        )
    return [_feedback_out(f) for f in list_feedback_received(db, current_user.id)]
