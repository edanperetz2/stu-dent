import threading
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationKind, ConversationParticipant, Message
from app.models.user import RoleEnum, User
from app.services.messaging import direct_key, get_or_create_conversation
from tests.conftest import engine
from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_patient,
    login,
    register,
    register_and_login,
)

# ---- Direct: patient <-> owning student (parity with the old direct_messages behavior) ----


def test_student_sends_message_to_own_patient(client):
    student_token = register_and_login(client, "msg-s1@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    response = client.post(
        f"/messages/direct/{patient_id}",
        json={"body": "Hello patient"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["body"] == "Hello patient"
    assert body["sender_id"] == student_id
    assert body["sender_name"] == "Test User"


def _student_id(client, student_token):
    return client.get("/users/me", headers=auth_header(student_token)).json()["id"]


def test_patient_sends_message_to_own_student(client):
    student_token = register_and_login(client, "msg-s2@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "msg-p2@example.com"
    )
    student_id = _student_id(client, student_token)

    response = client.post(
        f"/messages/direct/{student_id}",
        json={"body": "Hello student"},
        headers=auth_header(patient_token),
    )
    assert response.status_code == 201
    assert response.json()["sender_id"] == patient_id


def test_direct_thread_ordering_oldest_first(client):
    student_token = register_and_login(client, "msg-s3@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "msg-p3@example.com"
    )

    client.post(
        f"/messages/direct/{patient_id}", json={"body": "first"}, headers=auth_header(student_token)
    )
    student_id = _student_id(client, student_token)
    client.post(
        f"/messages/direct/{student_id}",
        json={"body": "second"},
        headers=auth_header(patient_token),
    )

    response = client.get(f"/messages/direct/{patient_id}", headers=auth_header(student_token))
    body = response.json()
    assert len(body) == 2
    assert body[0]["body"] == "first"
    assert body[1]["body"] == "second"


def test_marking_direct_thread_read(client):
    student_token = register_and_login(client, "msg-s4@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "msg-p4@example.com"
    )

    client.post(
        f"/messages/direct/{patient_id}",
        json={"body": "from student"},
        headers=auth_header(student_token),
    )

    response = client.post(
        f"/messages/direct/{_student_id(client, student_token)}/read",
        headers=auth_header(patient_token),
    )
    assert response.status_code == 200
    assert response.json()["last_read_at"] is not None


def test_marking_read_on_nonexistent_thread_is_a_noop(client):
    student_token = register_and_login(client, "msg-s4b@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = client.post(
        f"/messages/direct/{patient_id}/read", headers=auth_header(student_token)
    )
    assert response.status_code == 200
    assert response.json()["last_read_at"] is not None


def test_marking_direct_thread_unread(client):
    student_token = register_and_login(client, "msg-s4c@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "msg-p4c@example.com"
    )

    client.post(
        f"/messages/direct/{patient_id}",
        json={"body": "from student"},
        headers=auth_header(student_token),
    )
    student_id = _student_id(client, student_token)
    client.post(f"/messages/direct/{student_id}/read", headers=auth_header(patient_token))

    response = client.post(
        f"/messages/direct/{student_id}/unread", headers=auth_header(patient_token)
    )
    assert response.status_code == 200
    assert response.json()["last_read_at"] is None


def test_marking_unread_on_nonexistent_thread_is_a_noop(client):
    student_token = register_and_login(client, "msg-s4d@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = client.post(
        f"/messages/direct/{patient_id}/unread", headers=auth_header(student_token)
    )
    assert response.status_code == 200
    assert response.json()["last_read_at"] is None


def test_third_party_gets_404_not_403(client):
    student_token = register_and_login(client, "msg-s7@example.com", role="student")
    other_student_token = register_and_login(client, "msg-s7b@example.com", role="student")
    attending_token = register_and_login(client, "msg-a7@example.com", role="attending")
    patient_id, _ = create_and_login_patient(client, student_token, "msg-p7@example.com")

    assert (
        client.get(
            f"/messages/direct/{patient_id}", headers=auth_header(other_student_token)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/messages/direct/{patient_id}", headers=auth_header(attending_token)
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/messages/direct/{patient_id}",
            json={"body": "intrusion"},
            headers=auth_header(other_student_token),
        ).status_code
        == 404
    )


def test_message_to_nonexistent_user_404(client):
    student_token = register_and_login(client, "msg-s8@example.com", role="student")
    response = client.post(
        "/messages/direct/00000000-0000-0000-0000-000000000000",
        json={"body": "hi"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


def test_messages_require_authentication(client):
    other_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/messages/direct/{other_id}").status_code == 401
    assert client.post(f"/messages/direct/{other_id}", json={"body": "hi"}).status_code == 401


def test_unconfirmed_patient_can_view_but_not_send(client):
    student_token = register_and_login(client, "msg-s9@example.com", role="student")
    student_id = _student_id(client, student_token)
    register(
        client,
        "msg-p9@example.com",
        role="patient",
        full_name="Pending Patient",
        owner_student_id=student_id,
    )
    patient_token = login(client, "msg-p9@example.com").json()["access_token"]

    view = client.get(f"/messages/direct/{student_id}", headers=auth_header(patient_token))
    assert view.status_code == 200
    assert view.json() == []

    send = client.post(
        f"/messages/direct/{student_id}",
        json={"body": "hi"},
        headers=auth_header(patient_token),
    )
    assert send.status_code == 403


# ---- Direct: student <-> attending ----


def test_student_and_attending_can_message_each_other(client):
    student_token = register_and_login(client, "msg-s10@example.com", role="student")
    attending_token = register_and_login(client, "msg-a10@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]

    response = client.post(
        f"/messages/direct/{attending_id}",
        json={"body": "Question about a procedure"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 201

    student_id = _student_id(client, student_token)
    reply = client.post(
        f"/messages/direct/{student_id}",
        json={"body": "Sure, go ahead"},
        headers=auth_header(attending_token),
    )
    assert reply.status_code == 201

    thread = client.get(
        f"/messages/direct/{attending_id}", headers=auth_header(student_token)
    ).json()
    assert len(thread) == 2


def test_attending_cannot_message_patient_directly(client):
    student_token = register_and_login(client, "msg-s11@example.com", role="student")
    attending_token = register_and_login(client, "msg-a11@example.com", role="attending")
    patient_id = create_patient(client, student_token)

    response = client.post(
        f"/messages/direct/{patient_id}",
        json={"body": "hi"},
        headers=auth_header(attending_token),
    )
    assert response.status_code == 404


def test_patient_cannot_message_other_student(client):
    student_token = register_and_login(client, "msg-s12@example.com", role="student")
    other_student_token = register_and_login(client, "msg-s12b@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "msg-p12@example.com")
    other_student_id = _student_id(client, other_student_token)

    response = client.post(
        f"/messages/direct/{other_student_id}",
        json={"body": "hi"},
        headers=auth_header(patient_token),
    )
    assert response.status_code == 404


# ---- Contacts list ----


def test_student_contacts_include_own_patients_and_all_attendings(client):
    student_token = register_and_login(client, "msg-s13@example.com", role="student")
    register_and_login(client, "msg-a13@example.com", role="attending")
    patient_id = create_patient(client, student_token, full_name="My Patient")

    contacts = client.get("/messages/contacts", headers=auth_header(student_token)).json()
    roles = {c["role"] for c in contacts}
    ids = {c["id"] for c in contacts}
    assert "attending" in roles
    assert patient_id in ids


def test_patient_contacts_is_only_owning_student(client):
    student_token = register_and_login(client, "msg-s14@example.com", role="student")
    student_id = _student_id(client, student_token)
    _, patient_token = create_and_login_patient(client, student_token, "msg-p14@example.com")

    contacts = client.get("/messages/contacts", headers=auth_header(patient_token)).json()
    assert len(contacts) == 1
    assert contacts[0]["id"] == student_id


# ---- Shared admin inbox ----


def test_student_messages_admin_and_admin_replies(client):
    admin_token = register_and_login(client, "msg-admin1@example.com", role="admin")
    student_token = register_and_login(client, "msg-s15@example.com", role="student")
    student_id = _student_id(client, student_token)

    sent = client.post(
        "/messages/admin",
        json={"body": "Need help with my account"},
        headers=auth_header(student_token),
    )
    assert sent.status_code == 201

    inbox = client.get(
        f"/messages/admin-inbox/{student_id}", headers=auth_header(admin_token)
    ).json()
    assert len(inbox) == 1
    assert inbox[0]["body"] == "Need help with my account"

    reply = client.post(
        f"/messages/admin-inbox/{student_id}",
        json={"body": "Happy to help"},
        headers=auth_header(admin_token),
    )
    assert reply.status_code == 201

    thread = client.get("/messages/admin", headers=auth_header(student_token)).json()
    assert len(thread) == 2
    assert thread[1]["sender_name"] == "Test User"


def test_second_admin_sees_same_shared_inbox_thread(client):
    admin1_token = register_and_login(client, "msg-admin2@example.com", role="admin")
    admin2_token = register_and_login(client, "msg-admin3@example.com", role="admin")
    student_token = register_and_login(client, "msg-s16@example.com", role="student")
    student_id = _student_id(client, student_token)

    client.post(
        "/messages/admin", json={"body": "hello admins"}, headers=auth_header(student_token)
    )

    inbox_as_admin1 = client.get(
        f"/messages/admin-inbox/{student_id}", headers=auth_header(admin1_token)
    ).json()
    inbox_as_admin2 = client.get(
        f"/messages/admin-inbox/{student_id}", headers=auth_header(admin2_token)
    ).json()
    assert len(inbox_as_admin1) == len(inbox_as_admin2) == 1


def test_non_admin_cannot_use_admin_inbox_route(client):
    student_token = register_and_login(client, "msg-s17@example.com", role="student")
    other_id = _student_id(client, student_token)

    response = client.get(f"/messages/admin-inbox/{other_id}", headers=auth_header(student_token))
    assert response.status_code == 403


def test_admin_contacts_include_every_active_non_admin_user(client):
    admin_token = register_and_login(client, "msg-admin4@example.com", role="admin")
    student_token = register_and_login(client, "msg-s18@example.com", role="student")
    student_id = _student_id(client, student_token)

    contacts = client.get("/messages/contacts", headers=auth_header(admin_token)).json()
    ids = {c["id"] for c in contacts}
    assert student_id in ids


# ---- Group chats ----


def test_student_creates_group_and_sends_message(client):
    student1_token = register_and_login(client, "msg-s19@example.com", role="student")
    student2_id = _student_id(
        client, register_and_login(client, "msg-s19b@example.com", role="student")
    )
    attending_id = client.get(
        "/users/me",
        headers=auth_header(register_and_login(client, "msg-a19@example.com", role="attending")),
    ).json()["id"]

    created = client.post(
        "/messages/groups",
        json={"title": "Study group", "participant_ids": [student2_id, attending_id]},
        headers=auth_header(student1_token),
    )
    assert created.status_code == 201
    group = created.json()
    assert group["title"] == "Study group"
    assert len(group["participant_ids"]) == 3

    sent = client.post(
        f"/messages/groups/{group['id']}",
        json={"body": "Welcome everyone"},
        headers=auth_header(student1_token),
    )
    assert sent.status_code == 201
    assert sent.json()["conversation_id"] == group["id"]


def test_attending_can_create_group(client):
    attending_token = register_and_login(client, "msg-a20@example.com", role="attending")
    student_id = _student_id(
        client, register_and_login(client, "msg-s20@example.com", role="student")
    )

    response = client.post(
        "/messages/groups",
        json={"title": "Mentor group", "participant_ids": [student_id]},
        headers=auth_header(attending_token),
    )
    assert response.status_code == 201


def test_patient_cannot_create_group(client):
    student_token = register_and_login(client, "msg-s21@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "msg-p21@example.com")
    student_id = _student_id(client, student_token)

    response = client.post(
        "/messages/groups",
        json={"title": "Not allowed", "participant_ids": [student_id]},
        headers=auth_header(patient_token),
    )
    assert response.status_code == 403


def test_group_rejects_patient_participant(client):
    student_token = register_and_login(client, "msg-s22@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = client.post(
        "/messages/groups",
        json={"title": "Bad group", "participant_ids": [patient_id]},
        headers=auth_header(student_token),
    )
    assert response.status_code == 422


def test_non_participant_cannot_view_group(client):
    student1_token = register_and_login(client, "msg-s23@example.com", role="student")
    student2_token = register_and_login(client, "msg-s23b@example.com", role="student")
    student3_id = _student_id(
        client, register_and_login(client, "msg-s23c@example.com", role="student")
    )

    group = client.post(
        "/messages/groups",
        json={"title": "Exclusive", "participant_ids": [student3_id]},
        headers=auth_header(student1_token),
    ).json()

    response = client.get(f"/messages/groups/{group['id']}", headers=auth_header(student2_token))
    assert response.status_code == 404


def test_group_appears_in_list_for_all_participants(client):
    student1_token = register_and_login(client, "msg-s24@example.com", role="student")
    student2_token = register_and_login(client, "msg-s24b@example.com", role="student")
    student2_id = _student_id(client, student2_token)

    client.post(
        "/messages/groups",
        json={"title": "Shared group", "participant_ids": [student2_id]},
        headers=auth_header(student1_token),
    )

    groups_for_2 = client.get("/messages/groups", headers=auth_header(student2_token)).json()
    assert any(g["title"] == "Shared group" for g in groups_for_2)


# ---- Unread count (drives the Messages nav badge) --------------------------


def test_unread_count_reflects_new_message_and_own_messages_dont_count(client):
    student_token = register_and_login(client, "msg-s25@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "msg-p25@example.com"
    )

    assert client.get("/messages/unread-count", headers=auth_header(student_token)).json() == {
        "count": 0
    }

    client.post(
        f"/messages/direct/{_student_id(client, student_token)}",
        json={"body": "hi"},
        headers=auth_header(patient_token),
    )

    # The sender never counts their own message as unread for themselves.
    assert client.get("/messages/unread-count", headers=auth_header(patient_token)).json() == {
        "count": 0
    }
    assert client.get("/messages/unread-count", headers=auth_header(student_token)).json() == {
        "count": 1
    }


def test_unread_count_resets_after_read_and_returns_after_unread(client):
    student_token = register_and_login(client, "msg-s26@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "msg-p26@example.com"
    )
    student_id = _student_id(client, student_token)

    client.post(
        f"/messages/direct/{student_id}", json={"body": "hi"}, headers=auth_header(patient_token)
    )
    assert (
        client.get("/messages/unread-count", headers=auth_header(student_token)).json()["count"]
        == 1
    )

    client.post(f"/messages/direct/{patient_id}/read", headers=auth_header(student_token))
    assert (
        client.get("/messages/unread-count", headers=auth_header(student_token)).json()["count"]
        == 0
    )

    client.post(f"/messages/direct/{patient_id}/unread", headers=auth_header(student_token))
    assert (
        client.get("/messages/unread-count", headers=auth_header(student_token)).json()["count"]
        == 1
    )


def test_unread_count_uses_sequence_not_created_at_so_clock_skew_cant_hide_a_new_message(
    client, db_session
):
    """Regression test for the created_at-vs-last_read_at clock mismatch:
    Message.created_at is stamped by Postgres's transaction-start clock
    (func.now()), while last_read_at was stamped by this API server's own
    Python clock (datetime.now(UTC)) -- two different clock sources for
    the same "when did this happen" question. Directly backdates a brand
    new message's created_at to before the read receipt's timestamp (the
    same shape ordinary clock skew or round-trip timing could produce) and
    confirms it still counts as unread -- proving the comparison now keys
    off Message.sequence (which is really, unambiguously ordered by
    insertion) rather than the two mismatched clocks.
    """
    student_token = register_and_login(client, "msg-s26b@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "msg-p26b@example.com"
    )
    student_id = _student_id(client, student_token)

    client.post(
        f"/messages/direct/{student_id}", json={"body": "first"}, headers=auth_header(patient_token)
    )
    client.post(f"/messages/direct/{patient_id}/read", headers=auth_header(student_token))
    assert (
        client.get("/messages/unread-count", headers=auth_header(student_token)).json()["count"]
        == 0
    )

    participant = db_session.scalar(
        select(ConversationParticipant).where(ConversationParticipant.user_id == student_id)
    )
    read_at = participant.last_read_at
    assert read_at is not None

    conversation = db_session.get(Conversation, participant.conversation_id)
    # A real new message, inserted (and so sequenced) after the read --
    # but with created_at deliberately stamped *before* last_read_at, the
    # exact shape clock skew between the two sources could produce.
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=uuid.UUID(patient_id),
            body="skewed",
            created_at=read_at - timedelta(seconds=5),
        )
    )
    db_session.commit()

    assert (
        client.get("/messages/unread-count", headers=auth_header(student_token)).json()["count"]
        == 1
    )


def test_unread_count_includes_admin_thread_no_admin_has_touched_yet(client):
    """The shared admin inbox never adds a specific admin as a participant
    when a thread is first created -- an admin's unread count must still
    pick up a brand-new thread nobody on the admin side has opened yet,
    not just ones they've already replied to or explicitly marked."""
    admin_token = register_and_login(client, "msg-admin27@example.com", role="admin")
    student_token = register_and_login(client, "msg-s27@example.com", role="student")

    assert (
        client.get("/messages/unread-count", headers=auth_header(admin_token)).json()["count"] == 0
    )

    client.post(
        "/messages/admin", json={"body": "first ever message"}, headers=auth_header(student_token)
    )

    assert (
        client.get("/messages/unread-count", headers=auth_header(admin_token)).json()["count"] == 1
    )

    student_id = _student_id(client, student_token)
    client.post(f"/messages/admin-inbox/{student_id}/read", headers=auth_header(admin_token))
    assert (
        client.get("/messages/unread-count", headers=auth_header(admin_token)).json()["count"] == 0
    )


# ---- Thread summaries (drives the sidebar's unread indicator + sort) ------


def _summary_for(client, token, target_key):
    body = client.get("/messages/thread-summaries", headers=auth_header(token)).json()
    return next((s for s in body if s["target_key"] == target_key), None)


def test_thread_summary_marks_direct_contact_unread_with_last_message_time(client):
    student_token = register_and_login(client, "msg-s28@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "msg-p28@example.com"
    )
    student_id = _student_id(client, student_token)

    assert client.get("/messages/thread-summaries", headers=auth_header(student_token)).json() == []

    sent = client.post(
        f"/messages/direct/{student_id}", json={"body": "hi"}, headers=auth_header(patient_token)
    ).json()

    summary = _summary_for(client, student_token, f"direct:{patient_id}")
    assert summary is not None
    assert summary["has_unread"] is True
    assert summary["last_message_at"] == sent["created_at"]

    client.post(f"/messages/direct/{patient_id}/read", headers=auth_header(student_token))
    summary = _summary_for(client, student_token, f"direct:{patient_id}")
    assert summary["has_unread"] is False
    # Marking read doesn't erase the thread or its last-activity time.
    assert summary["last_message_at"] == sent["created_at"]


def test_thread_summary_marks_own_admin_thread_as_admin_self(client):
    # Admin reaches out first, before the student has ever touched the
    # thread -- their participant row starts out with last_read_at NULL,
    # so this doesn't depend on comparing a real read timestamp against a
    # same-transaction message timestamp (see the untouched-thread test
    # below for that comparison instead).
    student_token = register_and_login(client, "msg-s29@example.com", role="student")
    admin_token = register_and_login(client, "msg-admin29@example.com", role="admin")
    student_id = _student_id(client, student_token)

    client.post(
        f"/messages/admin-inbox/{student_id}",
        json={"body": "reaching out"},
        headers=auth_header(admin_token),
    )

    summary = _summary_for(client, student_token, "admin:self")
    assert summary is not None
    assert summary["has_unread"] is True

    client.post("/messages/admin/read", headers=auth_header(student_token))
    summary = _summary_for(client, student_token, "admin:self")
    assert summary["has_unread"] is False


def test_thread_summary_marks_admin_inbox_by_owner_id_including_untouched(client):
    admin_token = register_and_login(client, "msg-admin30@example.com", role="admin")
    student_token = register_and_login(client, "msg-s30@example.com", role="student")
    student_id = _student_id(client, student_token)

    client.post(
        "/messages/admin", json={"body": "brand new thread"}, headers=auth_header(student_token)
    )

    summary = _summary_for(client, admin_token, f"admin:{student_id}")
    assert summary is not None
    assert summary["has_unread"] is True

    client.post(f"/messages/admin-inbox/{student_id}/read", headers=auth_header(admin_token))
    summary = _summary_for(client, admin_token, f"admin:{student_id}")
    assert summary["has_unread"] is False


def test_thread_summary_marks_group_and_updates_last_message_time(client):
    student1_token = register_and_login(client, "msg-s31@example.com", role="student")
    student2_token = register_and_login(client, "msg-s31b@example.com", role="student")
    student2_id = _student_id(client, student2_token)

    group = client.post(
        "/messages/groups",
        json={"title": "Study group", "participant_ids": [student2_id]},
        headers=auth_header(student1_token),
    ).json()

    # A group with no messages yet still shows up (participants are added
    # at creation time), just with no last-activity timestamp.
    summary = _summary_for(client, student2_token, f"group:{group['id']}")
    assert summary is not None
    assert summary["has_unread"] is False
    assert summary["last_message_at"] is None

    sent = client.post(
        f"/messages/groups/{group['id']}",
        json={"body": "hey team"},
        headers=auth_header(student1_token),
    ).json()

    summary = _summary_for(client, student2_token, f"group:{group['id']}")
    assert summary["has_unread"] is True
    assert summary["last_message_at"] == sent["created_at"]


def test_get_or_create_conversation_rescues_concurrent_duplicate_insert():
    """Real DB-level concurrency guarantee (same pattern as
    test_appointment_conflicts.py::test_concurrent_overlapping_bookings_only_one_commits),
    bypassing the client/db_session fixture entirely -- that fixture wraps
    everything in one connection + SAVEPOINT rolled back at teardown, so
    rows created through it are invisible to another connection, and the
    fixture's own transaction can't observe two independent Sessions
    racing anyway. This uses the real `engine` and two independent
    `Session`s throughout (setup, the race itself, and cleanup) to prove
    get_or_create_conversation's SAVEPOINT-based rescue actually works
    under a real concurrent duplicate-key insert, not just the happy path
    where the row already exists before the function is ever called.
    """
    setup_session = Session(bind=engine)
    student_id = patient_id = None
    try:
        student = User(
            email="msg-race-student@example.com",
            hashed_password="x",
            role=RoleEnum.student,
            full_name="Race Student",
        )
        setup_session.add(student)
        setup_session.flush()
        patient = User(
            email="msg-race-patient@example.com",
            hashed_password="x",
            role=RoleEnum.patient,
            full_name="Race Patient",
            owner_student_id=student.id,
            owner_confirmed_at=datetime.now(UTC),
        )
        setup_session.add(patient)
        setup_session.commit()
        student_id, patient_id = student.id, patient.id
    finally:
        setup_session.close()

    key = direct_key(student_id, patient_id)

    barrier = threading.Barrier(2)
    results: dict[str, str] = {}
    conversation_ids: dict[str, str] = {}

    def _attempt(name: str) -> None:
        session = Session(bind=engine)
        try:
            barrier.wait()
            conversation = get_or_create_conversation(
                session,
                kind=ConversationKind.direct,
                key=key,
                participant_ids=[student_id, patient_id],
            )
            session.commit()
            results[name] = "ok"
            conversation_ids[name] = str(conversation.id)
        except Exception:
            results[name] = "error"
        finally:
            session.close()

    thread_a = threading.Thread(target=_attempt, args=("a",))
    thread_b = threading.Thread(target=_attempt, args=("b",))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    try:
        assert results == {"a": "ok", "b": "ok"}
        assert conversation_ids["a"] == conversation_ids["b"]

        cleanup_session = Session(bind=engine)
        try:
            count = (
                cleanup_session.query(Conversation).filter(Conversation.direct_key == key).count()
            )
            assert count == 1
        finally:
            cleanup_session.close()
    finally:
        teardown_session = Session(bind=engine)
        try:
            conversation_ids_to_delete = [
                row.id
                for row in teardown_session.query(Conversation).filter(
                    Conversation.direct_key == key
                )
            ]
            if conversation_ids_to_delete:
                teardown_session.query(ConversationParticipant).filter(
                    ConversationParticipant.conversation_id.in_(conversation_ids_to_delete)
                ).delete(synchronize_session=False)
                teardown_session.query(Conversation).filter(
                    Conversation.id.in_(conversation_ids_to_delete)
                ).delete(synchronize_session=False)
            if patient_id is not None:
                teardown_session.query(User).filter(User.id == patient_id).delete()
            if student_id is not None:
                teardown_session.query(User).filter(User.id == student_id).delete()
            teardown_session.commit()
        finally:
            teardown_session.close()
