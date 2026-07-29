"""Populate the local database with realistic demo data.

Invoked the same way as the worker (`python -m app.seed_demo`), not as a
FastAPI route -- direct DB access via SessionLocal, no HTTP round trip to
itself. Idempotent: if the sentinel demo admin already exists, this is a
no-op, so re-running is always safe.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.conversation import Conversation, ConversationKind, ConversationParticipant, Message
from app.models.equipment import Equipment
from app.models.forum_comment import ForumComment
from app.models.forum_comment_vote import ForumCommentVote
from app.models.forum_post import ForumPost
from app.models.forum_post_vote import ForumPostVote
from app.models.notification import NotificationType
from app.models.report import ReportPeriodType
from app.models.room import Room
from app.models.user import RoleEnum, User
from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus
from app.services.formatting import format_dt
from app.services.messaging import admin_key, direct_key
from app.services.notifications import notify
from app.services.report_assistant import generate_periodic_report
from app.services.scheduling import recompute_status, validate_participants

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED_ADMIN_EMAIL = "admin@stu-dent.demo"
DEMO_PASSWORD = "DemoPass123!"


def _seed_users(db: Session) -> dict[str, list[User] | User]:
    students = [
        User(
            email=f"student{i}@stu-dent.demo",
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name=f"Demo Student {i}",
            role=RoleEnum.student,
        )
        for i in (1, 2, 3)
    ]
    attendings = [
        User(
            email=f"attending{i}@stu-dent.demo",
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name=f"Dr. Demo Attending {i}",
            role=RoleEnum.attending,
        )
        for i in (1, 2)
    ]
    admin = User(
        email=SEED_ADMIN_EMAIL,
        hashed_password=hash_password(DEMO_PASSWORD),
        full_name="Demo Admin",
        role=RoleEnum.admin,
    )
    db.add_all([*students, *attendings, admin])
    db.flush()
    return {"students": students, "attendings": attendings, "admin": admin}


def _seed_rooms_and_equipment(db: Session) -> tuple[list[Room], list[Equipment]]:
    rooms = [Room(name="Operatory 1"), Room(name="Operatory 2")]
    equipment = [
        Equipment(name="Panoramic X-Ray", equipment_type="imaging"),
        Equipment(name="Ultrasonic Scaler", equipment_type="hygiene"),
        Equipment(name="Curing Light", equipment_type="restorative"),
    ]
    db.add_all([*rooms, *equipment])
    db.flush()
    return rooms, equipment


def _seed_patients(db: Session, students: list[User]) -> list[User]:
    now = datetime.now(UTC)

    student_initiated = [
        User(
            email=f"patient{i}@stu-dent.demo",
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name=f"Demo Patient {i}",
            role=RoleEnum.patient,
            owner_student_id=students[i - 1].id,
            owner_confirmed_at=now,
            contact_phone=f"555-01{i:02d}",
        )
        for i in (1, 2, 3)
    ]

    self_registered_confirmed = User(
        email="patient4@stu-dent.demo",
        hashed_password=hash_password(DEMO_PASSWORD),
        full_name="Demo Patient 4",
        role=RoleEnum.patient,
        owner_student_id=students[0].id,
        owner_confirmed_at=now,
    )

    # Deliberately left pending -- demonstrates the confirm-flow UI and the
    # require_confirmed_patient() 403 gate live.
    self_registered_pending = User(
        email="patient5@stu-dent.demo",
        hashed_password=hash_password(DEMO_PASSWORD),
        full_name="Demo Patient 5",
        role=RoleEnum.patient,
        owner_student_id=students[1].id,
        owner_confirmed_at=None,
    )

    patients = [*student_initiated, self_registered_confirmed, self_registered_pending]
    db.add_all(patients)
    db.flush()

    # Mirrors POST /auth/register's real side effect for a self-registration.
    notify(
        db,
        notification_type=NotificationType.patient_registration_request,
        message=(
            f"{self_registered_pending.full_name} has requested to join your "
            "patient list. Confirm them to proceed."
        ),
        recipient_id=students[1].id,
    )

    return patients


def _seed_appointments(
    db: Session,
    students: list[User],
    patients: list[User],
    attendings: list[User],
    rooms: list[Room],
    equipment: list[Equipment],
) -> dict[str, Appointment]:
    now = datetime.now(UTC)
    s0, s1, s2 = students
    p0, p1, p2, p3, _p4_pending = patients
    a0, a1 = attendings
    r0, r1 = rooms
    e0, e1, _e2 = equipment

    def _at(days: float, hour: int = 10) -> tuple[datetime, datetime]:
        start = (now + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
        return start, start + timedelta(minutes=30)

    appointments: dict[str, Appointment] = {}

    # -- Active statuses (must not overlap per shared resource -- each gets
    # its own day, so the exclusion constraints never fire). --

    start, end = _at(4)
    validate_participants(
        db, student_id=s0.id, patient_id=p0.id, attending_id=a0.id, room_id=None, equipment_id=None
    )
    appt = Appointment(
        student_id=s0.id,
        patient_id=p0.id,
        attending_id=a0.id,
        start_time=start,
        end_time=end,
        student_confirmed_at=now,
    )
    recompute_status(appt)
    appointments["awaiting_confirmation"] = appt

    start, end = _at(2)
    validate_participants(
        db, student_id=s1.id, patient_id=p1.id, attending_id=None, room_id=None, equipment_id=None
    )
    appt = Appointment(
        student_id=s1.id, patient_id=p1.id, start_time=start, end_time=end, student_confirmed_at=now
    )
    recompute_status(appt)
    appointments["confirmed_near"] = appt

    start, end = _at(1)
    validate_participants(
        db,
        student_id=s2.id,
        patient_id=p2.id,
        attending_id=a1.id,
        room_id=r0.id,
        equipment_id=e0.id,
    )
    appt = Appointment(
        student_id=s2.id,
        patient_id=p2.id,
        attending_id=a1.id,
        room_id=r0.id,
        equipment_id=e0.id,
        start_time=start,
        end_time=end,
        student_confirmed_at=now,
        attending_approved_at=now,
    )
    recompute_status(appt)
    appointments["confirmed_with_attending"] = appt

    start, end = _at(-1)
    validate_participants(
        db, student_id=s0.id, patient_id=p3.id, attending_id=None, room_id=None, equipment_id=None
    )
    appt = Appointment(
        student_id=s0.id, patient_id=p3.id, start_time=start, end_time=end, student_confirmed_at=now
    )
    recompute_status(appt)
    appointments["confirmed_past"] = appt

    start, end = _at(5)
    validate_participants(
        db, student_id=s1.id, patient_id=p1.id, attending_id=a0.id, room_id=None, equipment_id=None
    )
    appt = Appointment(
        student_id=s1.id,
        patient_id=p1.id,
        attending_id=a0.id,
        start_time=start,
        end_time=end,
        student_confirmed_at=now,
    )
    recompute_status(appt, time_changed=True)
    appointments["rescheduling_requested"] = appt

    # -- Non-active statuses: never participate in the exclusion
    # constraints, so resource/patient reuse across these is fine. --

    start, end = _at(6)
    validate_participants(
        db, student_id=s0.id, patient_id=p0.id, attending_id=None, room_id=None, equipment_id=None
    )
    appt = Appointment(student_id=s0.id, patient_id=p0.id, start_time=start, end_time=end)
    recompute_status(appt)
    appointments["proposed"] = appt

    start, end = _at(-3)
    appt = Appointment(
        student_id=s2.id,
        patient_id=p2.id,
        start_time=start,
        end_time=end,
        student_confirmed_at=now - timedelta(days=4),
        status=AppointmentStatus.cancelled,
    )
    appointments["cancelled"] = appt

    start, end = _at(-5)
    appt = Appointment(
        student_id=s1.id,
        patient_id=p1.id,
        attending_id=a1.id,
        room_id=r1.id,
        equipment_id=e1.id,
        start_time=start,
        end_time=end,
        student_confirmed_at=now - timedelta(days=6),
        attending_approved_at=now - timedelta(days=6),
        status=AppointmentStatus.completed,
    )
    appointments["completed"] = appt

    start, end = _at(-4)
    appt = Appointment(
        student_id=s0.id,
        patient_id=p3.id,
        start_time=start,
        end_time=end,
        student_confirmed_at=now - timedelta(days=5),
        status=AppointmentStatus.no_show,
    )
    appointments["no_show"] = appt

    db.add_all(appointments.values())
    db.flush()
    return appointments


def _seed_waitlist(
    db: Session, students: list[User], patients: list[User], attendings: list[User]
) -> list[WaitlistEntry]:
    now = datetime.now(UTC)
    entries = [
        WaitlistEntry(
            student_id=students[0].id,
            patient_id=patients[0].id,
            attending_id=attendings[0].id,
            start_time=now + timedelta(days=3, hours=2),
            end_time=now + timedelta(days=3, hours=3),
            student_confirmed_at=now,
            conflict_resource_types=["attending"],
            status=WaitlistStatus.active,
        ),
        WaitlistEntry(
            student_id=students[2].id,
            patient_id=patients[2].id,
            start_time=now + timedelta(days=7),
            end_time=now + timedelta(days=7, hours=1),
            student_confirmed_at=now,
            conflict_resource_types=["patient"],
            status=WaitlistStatus.active,
        ),
    ]
    db.add_all(entries)
    db.flush()
    return entries


def _seed_notifications(
    db: Session,
    students: list[User],
    patients: list[User],
    appointments: dict[str, Appointment],
) -> None:
    reminder_appt = appointments["confirmed_with_attending"]
    expired_appt = appointments["cancelled"]

    notify(
        db,
        notification_type=NotificationType.appointment_reminder,
        message=f"Reminder: appointment scheduled for {format_dt(reminder_appt.start_time)}.",
        recipient_id=students[2].id,
        related_appointment_id=reminder_appt.id,
    )
    notify(
        db,
        notification_type=NotificationType.appointment_reminder,
        message=f"Reminder: appointment scheduled for {format_dt(reminder_appt.start_time)}.",
        recipient_id=patients[2].id,
        related_appointment_id=reminder_appt.id,
    )
    notify(
        db,
        notification_type=NotificationType.appointment_expired,
        message="Your appointment request expired because it was never confirmed in time.",
        recipient_id=students[2].id,
        related_appointment_id=expired_appt.id,
    )
    slot_notification = notify(
        db,
        notification_type=NotificationType.waitlist_slot_available,
        message="A slot matching your waitlist request is now available.",
        recipient_id=students[0].id,
    )
    slot_notification.read_at = datetime.now(UTC)


def _seed_forum(db: Session, students: list[User]) -> None:
    s0, s1, s2 = students

    post1 = ForumPost(
        author_student_id=s0.id,
        title="Tips for nervous pediatric patients?",
        body="Looking for advice on keeping young patients calm during first visits.",
    )
    post2 = ForumPost(
        author_student_id=s1.id,
        title="Best practice for composite shade matching?",
        body="What's everyone's approach to shade matching under different clinic lighting?",
    )
    db.add_all([post1, post2])
    db.flush()

    comment1 = ForumComment(
        post_id=post1.id, author_student_id=s1.id, body="Distraction techniques work well for me."
    )
    comment2 = ForumComment(
        post_id=post1.id, author_student_id=s2.id, body="Short appointments help a lot too."
    )
    comment3 = ForumComment(
        post_id=post2.id, author_student_id=s0.id, body="Natural light near a window is ideal."
    )
    comment4 = ForumComment(
        post_id=post2.id, author_student_id=s2.id, body="I use a shade guide under neutral LEDs."
    )
    db.add_all([comment1, comment2, comment3, comment4])
    db.flush()

    db.add_all(
        [
            ForumPostVote(post_id=post1.id, student_id=s1.id, value=1),
            ForumPostVote(post_id=post1.id, student_id=s2.id, value=1),
            ForumPostVote(post_id=post2.id, student_id=s0.id, value=1),
            ForumPostVote(post_id=post2.id, student_id=s2.id, value=-1),
            ForumCommentVote(comment_id=comment1.id, student_id=s0.id, value=1),
            ForumCommentVote(comment_id=comment1.id, student_id=s2.id, value=1),
            ForumCommentVote(comment_id=comment2.id, student_id=s0.id, value=-1),
        ]
    )
    db.flush()


def _seed_messages(
    db: Session,
    students: list[User],
    attendings: list[User],
    patients: list[User],
    admin: User,
) -> None:
    """One thread of each conversation kind, so all four messaging surfaces
    (patient<->student, student<->attending, the shared admin inbox, and a
    student/attending group chat) render real data out of the box.
    """
    student = students[1]
    patient = patients[1]
    now = datetime.now(UTC)

    # Direct: patient <-> owning student.
    patient_thread = Conversation(
        kind=ConversationKind.direct, direct_key=direct_key(student.id, patient.id)
    )
    db.add(patient_thread)
    db.flush()
    db.add_all(
        [
            ConversationParticipant(
                conversation_id=patient_thread.id, user_id=student.id, last_read_at=now
            ),
            ConversationParticipant(
                conversation_id=patient_thread.id,
                user_id=patient.id,
                last_read_at=now - timedelta(minutes=5),
            ),
        ]
    )
    exchanges = [
        (
            patient.id,
            "Hi, I wanted to ask about rescheduling my next visit.",
            now - timedelta(hours=2),
        ),
        (student.id, "Sure, what day works better for you?", now - timedelta(minutes=90)),
        (patient.id, "Would Thursday afternoon be possible?", now - timedelta(minutes=60)),
        (
            student.id,
            "Thursday afternoon works -- I'll update the appointment.",
            now - timedelta(minutes=30),
        ),
        (patient.id, "Great, thank you!", now - timedelta(minutes=5)),
    ]
    for sender_id, body, created_at in exchanges:
        db.add(
            Message(
                conversation_id=patient_thread.id,
                sender_id=sender_id,
                body=body,
                created_at=created_at,
            )
        )

    # Direct: student <-> attending.
    other_student = students[0]
    attending = attendings[0]
    attending_thread = Conversation(
        kind=ConversationKind.direct, direct_key=direct_key(other_student.id, attending.id)
    )
    db.add(attending_thread)
    db.flush()
    db.add_all(
        [
            ConversationParticipant(conversation_id=attending_thread.id, user_id=other_student.id),
            ConversationParticipant(conversation_id=attending_thread.id, user_id=attending.id),
        ]
    )
    db.add(
        Message(
            conversation_id=attending_thread.id,
            sender_id=other_student.id,
            body="Could you review my case notes before tomorrow's procedure?",
            created_at=now - timedelta(hours=1),
        )
    )
    db.add(
        Message(
            conversation_id=attending_thread.id,
            sender_id=attending.id,
            body="Sent some feedback over -- looks good overall.",
            created_at=now - timedelta(minutes=45),
        )
    )

    # Shared admin inbox: a patient reaching out to admin.
    admin_thread = Conversation(kind=ConversationKind.admin, direct_key=admin_key(patient.id))
    db.add(admin_thread)
    db.flush()
    db.add(ConversationParticipant(conversation_id=admin_thread.id, user_id=patient.id))
    db.add(
        Message(
            conversation_id=admin_thread.id,
            sender_id=patient.id,
            body="Hi, I'm having trouble logging in on the mobile site.",
            created_at=now - timedelta(hours=3),
        )
    )
    db.add(
        Message(
            conversation_id=admin_thread.id,
            sender_id=admin.id,
            body="Thanks for flagging it -- we're looking into it.",
            created_at=now - timedelta(hours=2, minutes=30),
        )
    )

    # Group chat among students/attendings.
    group = Conversation(kind=ConversationKind.group, title="Case review - Week 3")
    db.add(group)
    db.flush()
    db.add_all(
        [
            ConversationParticipant(conversation_id=group.id, user_id=students[0].id),
            ConversationParticipant(conversation_id=group.id, user_id=students[1].id),
            ConversationParticipant(conversation_id=group.id, user_id=attendings[0].id),
        ]
    )
    db.add(
        Message(
            conversation_id=group.id,
            sender_id=students[0].id,
            body="Sharing this week's tricky cases here.",
            created_at=now - timedelta(hours=4),
        )
    )
    db.add(
        Message(
            conversation_id=group.id,
            sender_id=attendings[0].id,
            body="Great idea -- I'll chime in after reviewing.",
            created_at=now - timedelta(hours=3, minutes=30),
        )
    )
    db.flush()


def _seed_reports(db: Session, students: list[User], attendings: list[User]) -> None:
    now = datetime.now(UTC)
    week_start = datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=7)

    for recipient in (students[0], attendings[0]):
        generate_periodic_report(
            db,
            recipient,
            period_type=ReportPeriodType.weekly,
            period_start=week_start,
            period_end=week_end,
            commit=False,
        )


def main() -> None:
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == SEED_ADMIN_EMAIL))
        if existing is not None:
            logger.info("Demo data already seeded (found %s) -- nothing to do.", SEED_ADMIN_EMAIL)
            return

        users = _seed_users(db)
        students = users["students"]
        attendings = users["attendings"]
        admin = users["admin"]

        rooms, equipment = _seed_rooms_and_equipment(db)
        patients = _seed_patients(db, students)
        appointments = _seed_appointments(db, students, patients, attendings, rooms, equipment)
        _seed_waitlist(db, students, patients, attendings)
        _seed_notifications(db, students, patients, appointments)
        _seed_forum(db, students)
        _seed_messages(db, students, attendings, patients, admin)
        _seed_reports(db, students, attendings)

        db.commit()

    print("=== Stu-Dent demo accounts (password for all: DemoPass123!) ===")
    print(f"admin:      {SEED_ADMIN_EMAIL}")
    for i in (1, 2, 3):
        print(f"student:    student{i}@stu-dent.demo")
    for i in (1, 2):
        print(f"attending:  attending{i}@stu-dent.demo")
    for i in (1, 2, 3, 4):
        print(f"patient:    patient{i}@stu-dent.demo  (confirmed)")
    print("patient:    patient5@stu-dent.demo  (PENDING -- not yet confirmed by owning student)")


if __name__ == "__main__":
    main()
