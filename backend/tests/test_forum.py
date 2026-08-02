import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes import forum as forum_routes
from app.models.audit_log import AuditLog
from app.models.forum_post import ForumPost
from app.models.forum_post_vote import ForumPostVote
from app.models.user import RoleEnum, User
from app.schemas.forum import VoteIn
from tests.conftest import engine
from tests.helpers import auth_header, create_and_login_patient, register_and_login


def _create_post(client, token, title="Title", body="Body"):
    return client.post(
        "/forum/posts", json={"title": title, "body": body}, headers=auth_header(token)
    )


def _create_comment(client, token, post_id, body="Comment"):
    return client.post(
        f"/forum/posts/{post_id}/comments", json={"body": body}, headers=auth_header(token)
    )


def test_student_creates_post(client):
    student_token = register_and_login(client, "forum-s1@example.com", role="student")
    response = _create_post(client, student_token)
    assert response.status_code == 201
    body = response.json()
    assert body["likes"] == 0
    assert body["dislikes"] == 0
    assert body["title"] == "Title"


def test_non_student_cannot_create_post(client):
    attending_token = register_and_login(client, "forum-a1@example.com", role="attending")
    admin_token = register_and_login(client, "forum-admin1@example.com", role="admin")
    student_token = register_and_login(client, "forum-s2@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "forum-p1@example.com")

    assert _create_post(client, attending_token).status_code == 403
    assert _create_post(client, admin_token).status_code == 403
    assert _create_post(client, patient_token).status_code == 403


def test_list_posts_visible_to_students_and_admin_only(client):
    student_token = register_and_login(client, "forum-s3@example.com", role="student")
    attending_token = register_and_login(client, "forum-a3@example.com", role="attending")
    admin_token = register_and_login(client, "forum-admin3@example.com", role="admin")
    _create_post(client, student_token)

    assert client.get("/forum/posts", headers=auth_header(student_token)).status_code == 200
    assert client.get("/forum/posts", headers=auth_header(admin_token)).status_code == 200
    assert client.get("/forum/posts", headers=auth_header(attending_token)).status_code == 403


def test_update_post_by_author(client):
    student_token = register_and_login(client, "forum-s4@example.com", role="student")
    post = _create_post(client, student_token).json()

    response = client.patch(
        f"/forum/posts/{post['id']}",
        json={"title": "New Title"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"


def test_update_post_by_non_author_forbidden(client):
    student_token = register_and_login(client, "forum-s5@example.com", role="student")
    other_student_token = register_and_login(client, "forum-s5b@example.com", role="student")
    post = _create_post(client, student_token).json()

    response = client.patch(
        f"/forum/posts/{post['id']}",
        json={"title": "Hijacked"},
        headers=auth_header(other_student_token),
    )
    assert response.status_code == 403


def test_delete_post_by_author(client):
    student_token = register_and_login(client, "forum-s6@example.com", role="student")
    post = _create_post(client, student_token).json()

    response = client.delete(f"/forum/posts/{post['id']}", headers=auth_header(student_token))
    assert response.status_code == 204

    get_response = client.get(f"/forum/posts/{post['id']}", headers=auth_header(student_token))
    assert get_response.status_code == 404


def test_delete_post_by_admin_moderation(client):
    student_token = register_and_login(client, "forum-s7@example.com", role="student")
    admin_token = register_and_login(client, "forum-admin7@example.com", role="admin")
    post = _create_post(client, student_token).json()

    response = client.delete(f"/forum/posts/{post['id']}", headers=auth_header(admin_token))
    assert response.status_code == 204


def test_delete_post_by_non_author_non_admin_forbidden(client):
    student_token = register_and_login(client, "forum-s8@example.com", role="student")
    other_student_token = register_and_login(client, "forum-s8b@example.com", role="student")
    post = _create_post(client, student_token).json()

    response = client.delete(f"/forum/posts/{post['id']}", headers=auth_header(other_student_token))
    assert response.status_code == 403


def test_create_and_list_comments(client):
    student_token = register_and_login(client, "forum-s9@example.com", role="student")
    other_student_token = register_and_login(client, "forum-s9b@example.com", role="student")
    post = _create_post(client, student_token).json()

    response = _create_comment(client, other_student_token, post["id"])
    assert response.status_code == 201
    assert response.json()["likes"] == 0
    assert response.json()["dislikes"] == 0

    listing = client.get(
        f"/forum/posts/{post['id']}/comments", headers=auth_header(student_token)
    ).json()
    assert len(listing) == 1


def test_delete_comment_by_author_and_admin(client):
    student_token = register_and_login(client, "forum-s10@example.com", role="student")
    admin_token = register_and_login(client, "forum-admin10@example.com", role="admin")
    post = _create_post(client, student_token).json()

    comment_a = _create_comment(client, student_token, post["id"]).json()
    delete_by_author = client.delete(
        f"/forum/comments/{comment_a['id']}", headers=auth_header(student_token)
    )
    assert delete_by_author.status_code == 204

    comment_b = _create_comment(client, student_token, post["id"]).json()
    delete_by_admin = client.delete(
        f"/forum/comments/{comment_b['id']}", headers=auth_header(admin_token)
    )
    assert delete_by_admin.status_code == 204


def test_delete_comment_by_non_author_non_admin_forbidden(client):
    student_token = register_and_login(client, "forum-s11@example.com", role="student")
    other_student_token = register_and_login(client, "forum-s11b@example.com", role="student")
    post = _create_post(client, student_token).json()
    comment = _create_comment(client, student_token, post["id"]).json()

    response = client.delete(
        f"/forum/comments/{comment['id']}", headers=auth_header(other_student_token)
    )
    assert response.status_code == 403


def test_vote_on_post_upsert_changes_counts(client):
    student_token = register_and_login(client, "forum-s12@example.com", role="student")
    voter_token = register_and_login(client, "forum-s12b@example.com", role="student")
    post = _create_post(client, student_token).json()

    upvote = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_token)
    )
    assert upvote.status_code == 200
    assert upvote.json()["likes"] == 1
    assert upvote.json()["dislikes"] == 0

    switch_to_downvote = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": -1}, headers=auth_header(voter_token)
    )
    assert switch_to_downvote.status_code == 200
    assert switch_to_downvote.json()["likes"] == 0
    assert switch_to_downvote.json()["dislikes"] == 1


def test_remove_post_vote(client):
    student_token = register_and_login(client, "forum-s13@example.com", role="student")
    voter_token = register_and_login(client, "forum-s13b@example.com", role="student")
    post = _create_post(client, student_token).json()

    client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_token)
    )
    response = client.delete(f"/forum/posts/{post['id']}/vote", headers=auth_header(voter_token))
    assert response.status_code == 200
    assert response.json()["likes"] == 0
    assert response.json()["dislikes"] == 0


def test_vote_on_comment_upsert_and_remove(client):
    student_token = register_and_login(client, "forum-s14@example.com", role="student")
    voter_token = register_and_login(client, "forum-s14b@example.com", role="student")
    post = _create_post(client, student_token).json()
    comment = _create_comment(client, student_token, post["id"]).json()

    upvote = client.put(
        f"/forum/comments/{comment['id']}/vote",
        json={"value": 1},
        headers=auth_header(voter_token),
    )
    assert upvote.status_code == 200
    assert upvote.json()["likes"] == 1
    assert upvote.json()["dislikes"] == 0

    remove = client.delete(
        f"/forum/comments/{comment['id']}/vote", headers=auth_header(voter_token)
    )
    assert remove.status_code == 200
    assert remove.json()["likes"] == 0
    assert remove.json()["dislikes"] == 0


def test_vote_actions_write_audit_log_rows(client, db_session):
    student_token = register_and_login(client, "forum-s14c@example.com", role="student")
    voter_token = register_and_login(client, "forum-s14d@example.com", role="student")
    post = _create_post(client, student_token).json()
    comment = _create_comment(client, student_token, post["id"]).json()

    client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_token)
    )
    client.delete(f"/forum/posts/{post['id']}/vote", headers=auth_header(voter_token))
    client.put(
        f"/forum/comments/{comment['id']}/vote",
        json={"value": -1},
        headers=auth_header(voter_token),
    )
    client.delete(f"/forum/comments/{comment['id']}/vote", headers=auth_header(voter_token))

    actions = {
        row.action
        for row in db_session.scalars(
            select(AuditLog).where(AuditLog.target_type.in_(["forum_post", "forum_comment"]))
        ).all()
    }
    assert {
        "forum_post_vote",
        "forum_post_unvote",
        "forum_comment_vote",
        "forum_comment_unvote",
    } <= actions


def test_multiple_voters_aggregate_likes_and_dislikes(client):
    student_token = register_and_login(client, "forum-s15@example.com", role="student")
    voter_a = register_and_login(client, "forum-s15a@example.com", role="student")
    voter_b = register_and_login(client, "forum-s15b@example.com", role="student")
    voter_c = register_and_login(client, "forum-s15c@example.com", role="student")
    post = _create_post(client, student_token).json()

    client.put(f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_a))
    client.put(f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_b))
    response = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": -1}, headers=auth_header(voter_c)
    )
    assert response.json()["likes"] == 2
    assert response.json()["dislikes"] == 1


def test_invalid_vote_value_rejected(client):
    student_token = register_and_login(client, "forum-s16@example.com", role="student")
    post = _create_post(client, student_token).json()

    response = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 5}, headers=auth_header(student_token)
    )
    assert response.status_code == 422


def test_post_comment_count_reflects_active_comments(client):
    student_token = register_and_login(client, "forum-s18@example.com", role="student")
    other_student_token = register_and_login(client, "forum-s18b@example.com", role="student")
    post = _create_post(client, student_token).json()

    assert (
        client.get(f"/forum/posts/{post['id']}", headers=auth_header(student_token)).json()[
            "comment_count"
        ]
        == 0
    )

    comment_a = _create_comment(client, other_student_token, post["id"]).json()
    _create_comment(client, other_student_token, post["id"])
    listing = client.get("/forum/posts", headers=auth_header(student_token)).json()
    assert next(p for p in listing if p["id"] == post["id"])["comment_count"] == 2

    # Deleting one comment drops the count back down.
    client.delete(f"/forum/comments/{comment_a['id']}", headers=auth_header(other_student_token))
    detail = client.get(f"/forum/posts/{post['id']}", headers=auth_header(student_token)).json()
    assert detail["comment_count"] == 1


def test_post_and_comment_my_vote_reflects_current_users_own_vote(client):
    student_token = register_and_login(client, "forum-s19@example.com", role="student")
    voter_token = register_and_login(client, "forum-s19b@example.com", role="student")
    post = _create_post(client, student_token).json()
    comment = _create_comment(client, student_token, post["id"]).json()

    # No vote yet -- my_vote is None for both post and comment.
    listing = client.get("/forum/posts", headers=auth_header(voter_token)).json()
    assert next(p for p in listing if p["id"] == post["id"])["my_vote"] is None

    upvote = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_token)
    )
    assert upvote.json()["my_vote"] == 1

    # A different user's vote doesn't leak into this viewer's my_vote.
    other_view = client.get(f"/forum/posts/{post['id']}", headers=auth_header(student_token)).json()
    assert other_view["my_vote"] is None

    client.delete(f"/forum/posts/{post['id']}/vote", headers=auth_header(voter_token))
    after_remove = client.get(f"/forum/posts/{post['id']}", headers=auth_header(voter_token)).json()
    assert after_remove["my_vote"] is None

    comment_downvote = client.put(
        f"/forum/comments/{comment['id']}/vote",
        json={"value": -1},
        headers=auth_header(voter_token),
    )
    assert comment_downvote.json()["my_vote"] == -1


def test_comment_on_missing_post_404(client):
    student_token = register_and_login(client, "forum-s17@example.com", role="student")
    response = _create_comment(client, student_token, "00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_forum_requires_authentication(client):
    assert client.get("/forum/posts").status_code == 401
    assert client.post("/forum/posts", json={"title": "x", "body": "y"}).status_code == 401


def test_vote_on_post_rescues_concurrent_duplicate_insert():
    """Real DB-level concurrency guarantee (same pattern as
    test_messaging.py::test_get_or_create_conversation_rescues_concurrent_duplicate_insert),
    bypassing the client/db_session fixture entirely -- that fixture wraps
    everything in one connection + SAVEPOINT rolled back at teardown, so
    two independent Sessions can't race against each other through it.
    This uses the real `engine` and two independent `Session`s, with a
    `Barrier` so both threads race the same student's first vote on the
    same post at the same instant (a real double-click/two-open-tabs),
    proving vote_on_post's SAVEPOINT-based rescue actually works under a
    genuine concurrent duplicate-key insert on the (post_id, student_id)
    unique constraint, not just the already-exists happy path.
    """
    setup_session = Session(bind=engine)
    author_id = voter_id = post_id = None
    try:
        author = User(
            email="forum-race-author@example.com",
            hashed_password="x",
            role=RoleEnum.student,
            full_name="Race Author",
        )
        setup_session.add(author)
        setup_session.flush()
        voter = User(
            email="forum-race-voter@example.com",
            hashed_password="x",
            role=RoleEnum.student,
            full_name="Race Voter",
        )
        setup_session.add(voter)
        setup_session.flush()
        post = ForumPost(author_student_id=author.id, title="Race post", body="body")
        setup_session.add(post)
        setup_session.commit()
        author_id, voter_id, post_id = author.id, voter.id, post.id
    finally:
        setup_session.close()

    barrier = threading.Barrier(2)
    results: dict[str, str] = {}

    def _attempt(name: str) -> None:
        session = Session(bind=engine)
        try:
            voter_in_this_session = session.get(User, voter_id)
            barrier.wait()
            forum_routes.vote_on_post(
                post_id=post_id,
                payload=VoteIn(value=1),
                current_user=voter_in_this_session,
                db=session,
            )
            results[name] = "ok"
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

        cleanup_session = Session(bind=engine)
        try:
            votes = (
                cleanup_session.query(ForumPostVote)
                .filter(ForumPostVote.post_id == post_id, ForumPostVote.student_id == voter_id)
                .all()
            )
            assert len(votes) == 1
            assert votes[0].value == 1
        finally:
            cleanup_session.close()
    finally:
        teardown_session = Session(bind=engine)
        try:
            teardown_session.query(ForumPostVote).filter(ForumPostVote.post_id == post_id).delete()
            teardown_session.query(ForumPost).filter(ForumPost.id == post_id).delete()
            teardown_session.query(AuditLog).filter(
                AuditLog.actor_id.in_([author_id, voter_id])
            ).delete(synchronize_session=False)
            teardown_session.query(User).filter(User.id.in_([author_id, voter_id])).delete(
                synchronize_session=False
            )
            teardown_session.commit()
        finally:
            teardown_session.close()
