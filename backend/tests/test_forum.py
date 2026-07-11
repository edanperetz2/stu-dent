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
    assert body["score"] == 0
    assert body["title"] == "Title"


def test_non_student_cannot_create_post(client):
    attending_token = register_and_login(client, "forum-a1@example.com", role="attending")
    admin_token = register_and_login(client, "forum-admin1@example.com", role="admin")
    student_token = register_and_login(client, "forum-s2@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "forum-p1@example.com")

    assert _create_post(client, attending_token).status_code == 403
    assert _create_post(client, admin_token).status_code == 403
    # A patient token isn't a User principal_type at all, so require_role
    # rejects it at credential-validation time (401), not role-check (403) --
    # same distinction test_patient_auth.py already established in Phase 1.
    assert _create_post(client, patient_token).status_code == 401


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
    assert response.json()["score"] == 0

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


def test_vote_on_post_upsert_changes_score(client):
    student_token = register_and_login(client, "forum-s12@example.com", role="student")
    voter_token = register_and_login(client, "forum-s12b@example.com", role="student")
    post = _create_post(client, student_token).json()

    upvote = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_token)
    )
    assert upvote.status_code == 200
    assert upvote.json()["score"] == 1

    switch_to_downvote = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": -1}, headers=auth_header(voter_token)
    )
    assert switch_to_downvote.status_code == 200
    assert switch_to_downvote.json()["score"] == -1


def test_remove_post_vote(client):
    student_token = register_and_login(client, "forum-s13@example.com", role="student")
    voter_token = register_and_login(client, "forum-s13b@example.com", role="student")
    post = _create_post(client, student_token).json()

    client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_token)
    )
    response = client.delete(f"/forum/posts/{post['id']}/vote", headers=auth_header(voter_token))
    assert response.status_code == 200
    assert response.json()["score"] == 0


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
    assert upvote.json()["score"] == 1

    remove = client.delete(
        f"/forum/comments/{comment['id']}/vote", headers=auth_header(voter_token)
    )
    assert remove.status_code == 200
    assert remove.json()["score"] == 0


def test_multiple_voters_aggregate_score(client):
    student_token = register_and_login(client, "forum-s15@example.com", role="student")
    voter_a = register_and_login(client, "forum-s15a@example.com", role="student")
    voter_b = register_and_login(client, "forum-s15b@example.com", role="student")
    post = _create_post(client, student_token).json()

    client.put(f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_a))
    response = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 1}, headers=auth_header(voter_b)
    )
    assert response.json()["score"] == 2


def test_invalid_vote_value_rejected(client):
    student_token = register_and_login(client, "forum-s16@example.com", role="student")
    post = _create_post(client, student_token).json()

    response = client.put(
        f"/forum/posts/{post['id']}/vote", json={"value": 5}, headers=auth_header(student_token)
    )
    assert response.status_code == 422


def test_comment_on_missing_post_404(client):
    student_token = register_and_login(client, "forum-s17@example.com", role="student")
    response = _create_comment(client, student_token, "00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_forum_requires_authentication(client):
    assert client.get("/forum/posts").status_code == 401
    assert client.post("/forum/posts", json={"title": "x", "body": "y"}).status_code == 401
