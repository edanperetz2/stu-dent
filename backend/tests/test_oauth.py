from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.api.routes import oauth as oauth_routes
from app.config import Settings, settings
from app.models.oauth_identity import OAuthIdentity
from app.models.user import RoleEnum, User
from app.services.oauth import OAuthProfile, create_state
from tests.helpers import register


def _configure_google(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "google-secret")


def _fragment(location: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(location).fragment)


def test_google_settings_are_optional_without_environment(monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)

    isolated_settings = Settings(_env_file=None)

    assert isolated_settings.google_oauth_client_id is None
    assert isolated_settings.google_oauth_client_secret is None


def test_google_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "environment-client")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "environment-secret")

    isolated_settings = Settings(_env_file=None)

    assert isolated_settings.google_oauth_client_id == "environment-client"
    assert isolated_settings.google_oauth_client_secret == "environment-secret"


def test_google_start_returns_friendly_error_when_unconfigured(monkeypatch, client):
    monkeypatch.setattr(settings, "google_oauth_client_id", None)
    monkeypatch.setattr(settings, "google_oauth_client_secret", None)

    response = client.get(
        "/auth/oauth/google/start",
        params={"flow": "login"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert params["error"] == ["Google sign-in is not configured."]


def test_google_start_builds_server_oidc_redirect(monkeypatch, client):
    _configure_google(monkeypatch)

    response = client.get(
        "/auth/oauth/google/start",
        params={"flow": "register", "role": "student", "full_name": "Ada Lovelace"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    destination = urlparse(response.headers["location"])
    params = parse_qs(destination.query)
    assert f"{destination.scheme}://{destination.netloc}{destination.path}" == (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid email profile"]
    assert params["nonce"]
    assert params["state"]


def test_google_callback_links_verified_email_and_returns_app_token(
    monkeypatch, client, db_session
):
    _configure_google(monkeypatch)
    register(client, email="linked@example.com", full_name="Linked User")
    state, _ = create_state(
        "google",
        flow="login",
        role=None,
        owner_student_id=None,
        full_name=None,
        next_path="/reports",
    )
    monkeypatch.setattr(
        oauth_routes,
        "exchange_code",
        lambda *args, **kwargs: OAuthProfile(
            provider="google",
            subject="google-subject-1",
            email="linked@example.com",
            full_name="Ignored Provider Name",
        ),
    )

    response = client.get(
        "/auth/oauth/google/callback",
        params={"code": "one-time-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 303
    fragment = _fragment(response.headers["location"])
    assert fragment.get("token"), response.headers["location"]
    assert fragment["next"] == ["/reports"]
    user = db_session.scalar(select(User).where(User.email == "linked@example.com"))
    identity = db_session.scalar(
        select(OAuthIdentity).where(OAuthIdentity.subject == "google-subject-1")
    )
    assert identity is not None
    assert identity.user_id == user.id


def test_google_register_creates_social_only_account(monkeypatch, client, db_session):
    _configure_google(monkeypatch)
    state, _ = create_state(
        "google",
        flow="register",
        role=RoleEnum.attending,
        owner_student_id=None,
        full_name="Social Attending",
        next_path="/appointments",
    )
    monkeypatch.setattr(
        oauth_routes,
        "exchange_code",
        lambda *args, **kwargs: OAuthProfile(
            provider="google",
            subject="new-google-subject",
            email="social@example.com",
            full_name="Provider Name",
        ),
    )

    response = client.get(
        "/auth/oauth/google/callback",
        params={"code": "one-time-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert _fragment(response.headers["location"]).get("token"), response.headers["location"]
    user = db_session.scalar(select(User).where(User.email == "social@example.com"))
    assert user is not None
    assert user.full_name == "Social Attending"
    assert user.role == RoleEnum.attending


def test_apple_form_post_uses_first_authorization_name(monkeypatch, client, db_session):
    state, _ = create_state(
        "apple",
        flow="register",
        role=RoleEnum.student,
        owner_student_id=None,
        full_name=None,
        next_path="/appointments",
    )
    monkeypatch.setattr(
        oauth_routes,
        "exchange_code",
        lambda provider, code, nonce, *, apple_full_name=None: OAuthProfile(
            provider="apple",
            subject="apple-subject-1",
            email="private@privaterelay.appleid.com",
            full_name=apple_full_name,
        ),
    )

    response = client.post(
        "/auth/oauth/apple/callback",
        data={
            "code": "one-time-code",
            "state": state,
            "user": '{"name":{"firstName":"Grace","lastName":"Hopper"}}',
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    user = db_session.scalar(select(User).where(User.email == "private@privaterelay.appleid.com"))
    assert user is not None
    assert user.full_name == "Grace Hopper"


def test_tampered_state_returns_friendly_callback_error(client):
    response = client.get(
        "/auth/oauth/google/callback",
        params={"code": "one-time-code", "state": "tampered"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert "expired or could not be verified" in params["error"][0]
