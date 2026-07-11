def test_cors_allows_configured_frontend_origin(client):
    response = client.options(
        "/auth/register",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unlisted_origin(client):
    response = client.options(
        "/auth/register",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_frontend_origin_list_parses_comma_separated_origins():
    from app.config import Settings

    settings = Settings(frontend_origins="http://a.example.com, http://b.example.com")
    assert settings.frontend_origin_list == ["http://a.example.com", "http://b.example.com"]
