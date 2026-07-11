from app.jobs.reports import generate_scheduled_reports
from app.services import ollama_client
from tests.helpers import auth_header, register_and_login


def _mock_ollama_router(monkeypatch, *, classify=None, narrate=None):
    def fake(prompt: str):
        if "Classify" in prompt:
            return classify
        return narrate

    monkeypatch.setattr(ollama_client, "generate_json", fake)


def test_list_reports_requires_student_or_attending_role(client):
    admin_token = register_and_login(client, "rep-admin1@example.com", role="admin")
    response = client.get("/reports", headers=auth_header(admin_token))
    assert response.status_code == 403


def test_generate_report_now_creates_weekly_and_monthly(client, monkeypatch):
    _mock_ollama_router(monkeypatch, narrate={"summary": "Everything looks fine."})
    student_token = register_and_login(client, "rep-s1@example.com", role="student")

    response = client.post("/reports/generate", headers=auth_header(student_token))
    assert response.status_code == 201
    body = response.json()
    assert len(body) == 2
    assert {r["period_type"] for r in body} == {"weekly", "monthly"}
    for report in body:
        assert report["content"] == "Everything looks fine."
        assert report["question"] is None

    list_response = client.get("/reports", headers=auth_header(student_token))
    assert len(list_response.json()) == 2


def test_reports_scoped_to_own_recipient(client, monkeypatch):
    _mock_ollama_router(monkeypatch, narrate={"summary": "ok"})
    s1_token = register_and_login(client, "rep-s2@example.com", role="student")
    s2_token = register_and_login(client, "rep-s3@example.com", role="student")

    client.post("/reports/generate", headers=auth_header(s1_token))

    s2_reports = client.get("/reports", headers=auth_header(s2_token)).json()
    assert s2_reports == []


def test_ask_question_unsupported_type_returns_plain_message(client, monkeypatch):
    _mock_ollama_router(
        monkeypatch, classify={"question_type": "unsupported", "date_range_phrase": None}
    )
    student_token = register_and_login(client, "rep-s5@example.com", role="student")

    response = client.post(
        "/reports/ask",
        json={"question": "what's the weather"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["period_type"] == "ad_hoc"
    assert body["question"] == "what's the weather"
    assert "only answer questions about" in body["content"]


def test_ask_question_ollama_unavailable_returns_unsupported_message(client, monkeypatch):
    _mock_ollama_router(monkeypatch, classify=None)
    student_token = register_and_login(client, "rep-s6@example.com", role="student")

    response = client.post(
        "/reports/ask", json={"question": "anything"}, headers=auth_header(student_token)
    )
    assert response.status_code == 201
    assert "only answer questions about" in response.json()["content"]


def test_ask_question_time_impact_narrates_successfully(client, monkeypatch):
    _mock_ollama_router(
        monkeypatch,
        classify={"question_type": "time_impact", "date_range_phrase": "this week"},
        narrate={"summary": "No notable time was lost this week."},
    )
    student_token = register_and_login(client, "rep-s7@example.com", role="student")

    response = client.post(
        "/reports/ask",
        json={"question": "who wasted my time?"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["content"] == "No notable time was lost this week."
    assert body["period_type"] == "ad_hoc"


def test_ask_question_resource_utilization_narrates_successfully(client, monkeypatch):
    _mock_ollama_router(
        monkeypatch,
        classify={"question_type": "resource_utilization", "date_range_phrase": "this month"},
        narrate={"summary": "All rooms are used about evenly."},
    )
    student_token = register_and_login(client, "rep-s8@example.com", role="student")

    response = client.post(
        "/reports/ask",
        json={"question": "which room is underused?"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["content"] == "All rooms are used about evenly."


def test_generate_scheduled_reports_idempotent(client, db_session, monkeypatch):
    _mock_ollama_router(monkeypatch, narrate={"summary": "ok"})
    register_and_login(client, "rep-job-s1@example.com", role="student")

    first = generate_scheduled_reports(db_session)
    assert first == 2

    second = generate_scheduled_reports(db_session)
    assert second == 0
