import json

import psycopg
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation, ConversationKind, ConversationParticipant, Message
from app.models.notification import Notification, NotificationType
from app.models.user import RoleEnum, User
from app.realtime.events import CHANNEL
from app.services.notifications import notify
from tests.conftest import TEST_DATABASE_URL, engine
from tests.helpers import auth_header


def _sync_dsn() -> str:
    return TEST_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)


def test_notify_emits_pg_notify_for_listeners():
    """`notify()` must actually reach an independent LISTEN connection.

    This bypasses the client/db_session fixture on purpose: that fixture
    wraps each test in one outer transaction that's rolled back at
    teardown, and Postgres only delivers a NOTIFY once a transaction
    actually commits -- so this needs the real `engine` and a real
    `Session`, exactly like the appointment-conflict concurrency test does,
    for the same underlying reason.
    """
    setup_session = Session(bind=engine)
    user_id = None
    try:
        user = User(
            email="realtime-listener-check@example.com",
            hashed_password="x",
            role=RoleEnum.student,
            full_name="Realtime Check",
        )
        setup_session.add(user)
        setup_session.commit()
        user_id = user.id
    finally:
        setup_session.close()

    listen_conn = psycopg.connect(_sync_dsn(), autocommit=True)
    try:
        listen_conn.execute(f"LISTEN {CHANNEL}")

        notify_session = Session(bind=engine)
        try:
            notify(
                notify_session,
                notification_type=NotificationType.appointment_reminder,
                message="realtime check",
                recipient_id=user_id,
            )
            notify_session.commit()
        finally:
            notify_session.close()

        received = next(listen_conn.notifies(timeout=5, stop_after=1), None)
        assert received is not None, "expected a NOTIFY on the realtime channel"
        payload = json.loads(received.payload)
        assert payload["recipient_id"] == str(user_id)
        assert payload["event"] == "notification"
        assert payload["message"] == "realtime check"
    finally:
        listen_conn.close()
        cleanup_session = Session(bind=engine)
        try:
            cleanup_session.query(Notification).filter(
                Notification.recipient_id == user_id
            ).delete()
            cleanup_session.query(User).filter(User.id == user_id).delete()
            cleanup_session.commit()
        finally:
            cleanup_session.close()


def test_websocket_receives_direct_message_live():
    """Full same-process pipeline: HTTP request -> publish() -> pg_notify
    -> this test's own listener task -> ConnectionManager -> WebSocket.

    Needs a *real-commit* get_db override (not the SAVEPOINT-wrapped
    db_session fixture) for the same reason as the test above: the DM
    creation must actually commit for its NOTIFY to be delivered to the
    listener task this TestClient's own lifespan starts.
    """

    def _real_get_db():
        db = Session(bind=engine)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _real_get_db
    student_id = patient_id = None
    try:
        with TestClient(app) as real_client:
            setup_session = Session(bind=engine)
            try:
                student = User(
                    email="realtime-ws-student@example.com",
                    hashed_password="x",
                    role=RoleEnum.student,
                    full_name="Realtime WS Student",
                )
                setup_session.add(student)
                setup_session.flush()
                patient = User(
                    owner_student_id=student.id,
                    owner_confirmed_at=student.created_at,
                    role=RoleEnum.patient,
                    full_name="Realtime WS Patient",
                    email="realtime-ws-patient@example.com",
                    hashed_password="x",
                )
                setup_session.add(patient)
                setup_session.commit()
                student_id, patient_id = student.id, patient.id
            finally:
                setup_session.close()

            # hashed_password is a placeholder, not a real argon2 hash, so
            # tokens are minted directly rather than via /auth/login.
            patient_token = create_access_token(subject=patient_id, role=RoleEnum.patient.value)
            student_jwt = create_access_token(subject=student_id, role=RoleEnum.student.value)

            with real_client.websocket_connect(f"/ws?token={patient_token}") as websocket:
                response = real_client.post(
                    f"/messages/direct/{patient_id}",
                    json={"body": "live hello"},
                    headers=auth_header(student_jwt),
                )
                assert response.status_code == 201

                event = websocket.receive_json()
                assert event["event"] == "message"
                assert event["body"] == "live hello"
                assert event["recipient_id"] == str(patient_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        cleanup_session = Session(bind=engine)
        try:
            if patient_id is not None:
                cleanup_session.query(AuditLog).filter(AuditLog.actor_id == patient_id).delete()
            if student_id is not None:
                cleanup_session.query(AuditLog).filter(AuditLog.actor_id == student_id).delete()
            conversation = cleanup_session.scalar(
                select(Conversation).where(Conversation.direct_key.contains(str(patient_id)))
            )
            if conversation is not None:
                cleanup_session.query(Message).filter(
                    Message.conversation_id == conversation.id
                ).delete()
                cleanup_session.query(ConversationParticipant).filter(
                    ConversationParticipant.conversation_id == conversation.id
                ).delete()
                cleanup_session.query(Conversation).filter(
                    Conversation.id == conversation.id
                ).delete()
            if patient_id is not None:
                cleanup_session.query(User).filter(User.id == patient_id).delete()
            if student_id is not None:
                cleanup_session.query(User).filter(User.id == student_id).delete()
            cleanup_session.commit()
        finally:
            cleanup_session.close()


def test_websocket_broadcasts_group_message_to_every_other_participant():
    """Group chat is the one case where `_send_message` calls `publish()`
    more than once per send -- worth its own live check that every other
    participant actually gets a push, not just the first one.
    """

    def _real_get_db():
        db = Session(bind=engine)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _real_get_db
    student_ids: list = []
    conversation_id = None
    try:
        with TestClient(app) as real_client:
            setup_session = Session(bind=engine)
            try:
                students = [
                    User(
                        email=f"realtime-ws-group-{i}@example.com",
                        hashed_password="x",
                        role=RoleEnum.student,
                        full_name=f"Realtime WS Group Student {i}",
                    )
                    for i in range(3)
                ]
                setup_session.add_all(students)
                setup_session.flush()
                conversation = Conversation(kind=ConversationKind.group, title="Realtime group")
                setup_session.add(conversation)
                setup_session.flush()
                setup_session.add_all(
                    [
                        ConversationParticipant(conversation_id=conversation.id, user_id=s.id)
                        for s in students
                    ]
                )
                setup_session.commit()
                student_ids = [s.id for s in students]
                conversation_id = conversation.id
            finally:
                setup_session.close()

            sender_jwt = create_access_token(subject=student_ids[0], role=RoleEnum.student.value)
            listener_tokens = [
                create_access_token(subject=sid, role=RoleEnum.student.value)
                for sid in student_ids[1:]
            ]

            with (
                real_client.websocket_connect(f"/ws?token={listener_tokens[0]}") as ws1,
                real_client.websocket_connect(f"/ws?token={listener_tokens[1]}") as ws2,
            ):
                response = real_client.post(
                    f"/messages/groups/{conversation_id}",
                    json={"body": "hello group"},
                    headers=auth_header(sender_jwt),
                )
                assert response.status_code == 201

                event1 = ws1.receive_json()
                event2 = ws2.receive_json()
                for event, recipient_id in zip([event1, event2], student_ids[1:], strict=True):
                    assert event["event"] == "message"
                    assert event["body"] == "hello group"
                    assert event["recipient_id"] == str(recipient_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        cleanup_session = Session(bind=engine)
        try:
            for sid in student_ids:
                cleanup_session.query(AuditLog).filter(AuditLog.actor_id == sid).delete()
            if conversation_id is not None:
                cleanup_session.query(Message).filter(
                    Message.conversation_id == conversation_id
                ).delete()
                cleanup_session.query(ConversationParticipant).filter(
                    ConversationParticipant.conversation_id == conversation_id
                ).delete()
                cleanup_session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).delete()
            for sid in student_ids:
                cleanup_session.query(User).filter(User.id == sid).delete()
            cleanup_session.commit()
        finally:
            cleanup_session.close()
