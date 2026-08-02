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
        assert report["content_source"] == "ai"

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
    assert body["content_source"] == "unsupported"


def test_ask_question_ollama_unavailable_returns_assistant_unavailable_message(client, monkeypatch):
    # Distinct from a genuinely unsupported question -- the classify call
    # itself failed (Ollama unreachable), so the viewer should be told the
    # assistant is down, not that their question type isn't supported.
    _mock_ollama_router(monkeypatch, classify=None)
    student_token = register_and_login(client, "rep-s6@example.com", role="student")

    response = client.post(
        "/reports/ask", json={"question": "anything"}, headers=auth_header(student_token)
    )
    assert response.status_code == 201
    body = response.json()
    assert "currently unavailable" in body["content"]
    assert body["content_source"] == "unavailable"


def test_ask_question_unresolved_date_range_is_not_silently_answered_with_a_default_window(
    client, monkeypatch
):
    # Regression test: a real, supported question type with a date phrase
    # resolve_date_range() doesn't recognize used to silently fall back to
    # a generic last-30-days window with no indication the answered range
    # wasn't the one actually asked about.
    _mock_ollama_router(
        monkeypatch,
        classify={"question_type": "time_impact", "date_range_phrase": "yesterday"},
        narrate={"summary": "this should never be reached"},
    )
    student_token = register_and_login(client, "rep-s6b@example.com", role="student")

    response = client.post(
        "/reports/ask",
        json={"question": "who wasted my time yesterday?"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["content_source"] == "unresolved_date_range"
    assert "yesterday" in body["content"]
    assert "this should never be reached" not in body["content"]


def test_ask_question_malformed_classify_response_gets_a_distinct_message_from_unavailable(
    client, monkeypatch
):
    # Ollama responded (unlike the genuinely-unreachable case), just not
    # with something _ClassifyResponse can validate -- the message should
    # say so, not claim the assistant "couldn't be reached".
    _mock_ollama_router(monkeypatch, classify={"question_type": "not_a_real_type"})
    student_token = register_and_login(client, "rep-s6c@example.com", role="student")

    response = client.post(
        "/reports/ask", json={"question": "anything"}, headers=auth_header(student_token)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["content_source"] == "malformed_response"
    assert "couldn't be reached" not in body["content"]
    assert "format this app" in body["content"]


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
    assert body["content_source"] == "ai"


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
    assert body["content_source"] == "ai"


def test_generate_report_falls_back_when_model_returns_blank_summary(client, monkeypatch):
    # A real model can return technically-valid JSON with an empty/blank
    # "summary" -- this must fall back to the deterministic plain-English
    # summary rather than silently producing a blank report (found via live
    # testing), and must be flagged as a fallback, not real AI content.
    _mock_ollama_router(monkeypatch, narrate={"summary": "   "})
    student_token = register_and_login(client, "rep-s9@example.com", role="student")

    response = client.post("/reports/generate", headers=auth_header(student_token))
    assert response.status_code == 201
    for report in response.json():
        assert report["content"].strip() != ""
        assert "AI narration unavailable" in report["content"]
        assert report["content_source"] == "fallback_summary"


def test_generate_scheduled_reports_idempotent(client, db_session, monkeypatch):
    _mock_ollama_router(monkeypatch, narrate={"summary": "ok"})
    register_and_login(client, "rep-job-s1@example.com", role="student")

    first = generate_scheduled_reports(db_session)
    assert first == 2

    second = generate_scheduled_reports(db_session)
    assert second == 0


def test_generate_scheduled_reports_dedupes_resource_utilization_across_recipients(
    client, db_session, monkeypatch
):
    # resource_utilization is clinic-wide, not recipient-specific -- it
    # should be computed once per period_type per run, not once per
    # recipient, even though generate_periodic_report is still called once
    # per recipient.
    register_and_login(client, "rep-job-s4@example.com", role="student")
    register_and_login(client, "rep-job-s5@example.com", role="student")
    register_and_login(client, "rep-job-s6@example.com", role="student")
    _mock_ollama_router(monkeypatch, narrate={"summary": "ok"})

    from app.jobs import reports as reports_job
    from app.services import report_data

    real_resource_utilization = report_data.resource_utilization
    call_count = 0

    def counting_resource_utilization(db, **kwargs):
        nonlocal call_count
        call_count += 1
        return real_resource_utilization(db, **kwargs)

    monkeypatch.setattr(reports_job, "resource_utilization", counting_resource_utilization)

    generated = generate_scheduled_reports(db_session)
    assert generated == 6  # 3 recipients x 2 period types
    assert call_count == 2  # once per period type (weekly, monthly), not per recipient


def test_generate_scheduled_reports_one_recipient_failing_does_not_block_others(
    client, db_session, monkeypatch
):
    # A single bad Ollama response/exception for one recipient must not
    # abort the whole job -- everyone after them in the loop still gets
    # their report this pass.
    register_and_login(client, "rep-job-s2@example.com", role="student")
    register_and_login(client, "rep-job-s3@example.com", role="student")

    from app.services import report_assistant

    real_generate = report_assistant.generate_periodic_report
    call_count = 0

    def flaky_generate(db, recipient, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated Ollama failure")
        return real_generate(db, recipient, **kwargs)

    monkeypatch.setattr(report_assistant, "generate_periodic_report", flaky_generate)
    monkeypatch.setattr("app.jobs.reports.generate_periodic_report", flaky_generate)
    _mock_ollama_router(monkeypatch, narrate={"summary": "ok"})

    generated = generate_scheduled_reports(db_session)
    # 2 recipients x 2 period types = 4 attempts, 1 fails -> 3 succeed.
    assert generated == 3
