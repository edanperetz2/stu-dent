def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_unhealthy_when_db_is_unreachable(client, db_session, monkeypatch):
    # Regression test: /health used to be a hardcoded {"status": "ok"}
    # stub that never actually touched the DB -- a real DB outage
    # post-startup went unnoticed by the docker-compose healthcheck that
    # hits this exact endpoint.
    def _raise(*args, **kwargs):
        raise Exception("simulated DB outage")

    monkeypatch.setattr(db_session, "execute", _raise)

    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
