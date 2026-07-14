import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import ACTIVE_STATUSES, Appointment
from app.models.conversation import ConversationKind
from app.models.notification import NotificationType
from app.models.user import User
from app.services.messaging import admin_key, get_or_create_conversation, send_message
from app.services.notifications import notify


def notify_students_of_deactivation(
    db: Session,
    *,
    actor: User,
    resource_kind: Literal["room", "equipment"],
    resource_id: uuid.UUID,
    resource_name: str,
) -> None:
    """A room/equipment that was just deactivated may still be booked on
    upcoming appointments -- let each affected appointment's owning student
    know, through both the admin-inbox message thread and a Notification,
    so they see it whichever surface they check first (per explicit
    request -- see the "fixes" conversation this shipped in).
    """
    column = Appointment.room_id if resource_kind == "room" else Appointment.equipment_id
    now = datetime.now(UTC)
    affected = db.scalars(
        select(Appointment).where(
            column == resource_id,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.end_time > now,
        )
    )

    for appointment in affected:
        message_body = (
            f'The {resource_kind} "{resource_name}" used by your appointment on '
            f"{appointment.start_time.isoformat()} has just been deactivated. "
            "Please update this appointment with a new one."
        )
        conversation = get_or_create_conversation(
            db,
            kind=ConversationKind.admin,
            key=admin_key(appointment.student_id),
            participant_ids=[appointment.student_id],
        )
        send_message(
            db,
            conversation=conversation,
            sender=actor,
            body=message_body,
            recipient_ids=[appointment.student_id],
        )
        notify(
            db,
            notification_type=NotificationType.resource_deactivated,
            message=message_body,
            recipient_id=appointment.student_id,
            related_appointment_id=appointment.id,
        )
        db.commit()
