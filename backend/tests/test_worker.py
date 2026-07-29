import pytest

from app import worker


def _stub_jobs(**overrides):
    jobs = {name: (lambda db: 0) for name in worker._JOB_FUNCS}
    jobs.update(overrides)
    return jobs


def test_run_once_isolates_one_jobs_exception_from_the_rest(monkeypatch):
    calls = []

    def ok_job(db):
        calls.append("ok")
        return 1

    def broken_job(db):
        calls.append("broken")
        raise RuntimeError("boom")

    monkeypatch.setattr(
        worker,
        "_JOB_FUNCS",
        _stub_jobs(
            reactivate_expired_deactivations=ok_job,
            send_appointment_reminders=broken_job,
            expire_stale_appointments=ok_job,
            generate_scheduled_reports=ok_job,
            notify_unresolved_past_appointments=ok_job,
            notify_pending_feedback=ok_job,
        ),
    )

    worker.run_once()  # must not raise, even though one job did

    assert calls.count("ok") == 5
    assert calls.count("broken") == 1


def test_run_once_runs_reactivation_before_expiry(monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(
        worker,
        "_JOB_FUNCS",
        _stub_jobs(
            reactivate_expired_deactivations=lambda db: order.append("reactivate") or 0,
            expire_stale_appointments=lambda db: order.append("expire") or 0,
        ),
    )

    worker.run_once()

    assert order == ["reactivate", "expire"]


def test_main_loop_survives_run_once_raising(monkeypatch):
    monkeypatch.setattr(worker.settings, "job_poll_interval_seconds", 0)

    call_count = {"n": 0}

    def fake_run_once():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("boom")
        # SystemExit -- not a subclass of Exception, so main()'s own
        # `except Exception` (the thing under test) can't swallow it too
        # and turn this into a genuine infinite loop.
        raise SystemExit

    monkeypatch.setattr(worker, "run_once", fake_run_once)
    monkeypatch.setattr(worker.time, "sleep", lambda _seconds: None)

    with pytest.raises(SystemExit):
        worker.main()

    assert call_count["n"] == 2
