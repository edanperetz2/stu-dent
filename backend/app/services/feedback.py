import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.feedback import Feedback, FeedbackAuthorRole
from app.models.user import User


def authorize_feedback_author(appointment: Appointment, user: User) -> FeedbackAuthorRole:
    """Which role `user` would be giving feedback as on this appointment, or
    raise if they're not allowed to give feedback on it at all yet."""
    if user.id == appointment.patient_id:
        role = FeedbackAuthorRole.patient
    elif appointment.attending_id is not None and user.id == appointment.attending_id:
        role = FeedbackAuthorRole.attending
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the patient or attending on this appointment can give feedback",
        )

    if appointment.status != AppointmentStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback can only be given for a completed appointment",
        )

    return role


def list_pending_feedback(db: Session, user: User) -> list[Appointment]:
    """Completed appointments where `user` is a participant (patient or
    attending) but hasn't yet submitted feedback."""
    stmt = select(Appointment).where(
        Appointment.status == AppointmentStatus.completed,
        (Appointment.patient_id == user.id) | (Appointment.attending_id == user.id),
    )
    already_given = set(
        db.scalars(select(Feedback.appointment_id).where(Feedback.author_id == user.id))
    )
    return [a for a in db.scalars(stmt) if a.id not in already_given]


def list_feedback_given(db: Session, author_id: uuid.UUID) -> list[Feedback]:
    stmt = select(Feedback).where(Feedback.author_id == author_id)
    return list(db.scalars(stmt))


def list_feedback_received(db: Session, student_id: uuid.UUID) -> list[Feedback]:
    stmt = select(Feedback).where(Feedback.student_id == student_id)
    return list(db.scalars(stmt))
