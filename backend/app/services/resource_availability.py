import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import ACTIVE_STATUSES, Appointment
from app.models.conversation import ConversationKind
from app.models.notification import NotificationType
from app.models.user import User
from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus
from app.services.formatting import format_dt
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

    Also covers active waitlist entries targeting this resource: without
    this, a pending entry's student was never told their entry now wants a
    resource nobody deactivated it for their sake, and -- since
    find_conflicts() only checks for overlapping *active appointments*, not
    resource active status -- the entry could later silently auto-promote
    into booking the very resource that was just taken offline
    (services/waitlist.py::recheck_waitlist_for_freed_slot separately
    guards the promotion itself; this is the "let the student know" half).
    """
    appointment_column = (
        Appointment.room_id if resource_kind == "room" else Appointment.equipment_id
    )
    now = datetime.now(UTC)
    affected = db.scalars(
        select(Appointment).where(
            appointment_column == resource_id,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.end_time > now,
        )
    )

    for appointment in affected:
        message_body = (
            f'The {resource_kind} "{resource_name}" used by your appointment on '
            f"{format_dt(appointment.start_time)} has just been deactivated. "
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

    waitlist_column = (
        WaitlistEntry.room_id if resource_kind == "room" else WaitlistEntry.equipment_id
    )
    affected_entries = db.scalars(
        select(WaitlistEntry).where(
            waitlist_column == resource_id,
            WaitlistEntry.status == WaitlistStatus.active,
            WaitlistEntry.end_time > now,
        )
    )

    for entry in affected_entries:
        message_body = (
            f'The {resource_kind} "{resource_name}" your waitlist entry for '
            f"{format_dt(entry.start_time)} wants has just been deactivated. "
            "It won't be auto-booked into that resource -- update or cancel the "
            "entry once you've picked a replacement."
        )
        conversation = get_or_create_conversation(
            db,
            kind=ConversationKind.admin,
            key=admin_key(entry.student_id),
            participant_ids=[entry.student_id],
        )
        send_message(
            db,
            conversation=conversation,
            sender=actor,
            body=message_body,
            recipient_ids=[entry.student_id],
        )
        # No related_appointment_id -- a waitlist entry isn't one yet, and
        # Notification has no related_waitlist_entry_id column (a real
        # schema addition, out of scope for this fix).
        notify(
            db,
            notification_type=NotificationType.resource_deactivated,
            message=message_body,
            recipient_id=entry.student_id,
        )
        db.commit()
