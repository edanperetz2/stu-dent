import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.config import settings
from app.models.user import RoleEnum

OAuthProvider = Literal["google", "apple"]

_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 -- endpoint, not a secret
_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_APPLE_AUTHORIZE_URL = "https://appleid.apple.com/auth/authorize"
_APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"  # noqa: S105 -- endpoint, not a secret
_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


class OAuthError(Exception):
    pass


@dataclass(frozen=True)
class OAuthProfile:
    provider: OAuthProvider
    subject: str
    email: str
    full_name: str | None


def provider_is_configured(provider: OAuthProvider) -> bool:
    if provider == "google":
        return bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)
    return bool(
        settings.apple_oauth_client_id
        and settings.apple_oauth_team_id
        and settings.apple_oauth_key_id
        and settings.apple_oauth_private_key
    )


def callback_url(provider: OAuthProvider) -> str:
    return f"{settings.oauth_backend_public_url.rstrip('/')}/auth/oauth/{provider}/callback"


def create_state(
    provider: OAuthProvider,
    *,
    flow: Literal["login", "register"],
    role: RoleEnum | None,
    owner_student_id: uuid.UUID | None,
    full_name: str | None,
    next_path: str,
) -> tuple[str, str]:
    now = datetime.now(UTC)
    nonce = secrets.token_urlsafe(24)
    payload = {
        "purpose": "oauth_state",
        "provider": provider,
        "flow": flow,
        "nonce": nonce,
        "role": role.value if role else None,
        "owner_student_id": str(owner_student_id) if owner_student_id else None,
        "full_name": full_name,
        "next": next_path,
        "iat": now,
        "exp": now + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256"), nonce


def decode_state(state: str, expected_provider: OAuthProvider) -> dict[str, Any]:
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as err:
        raise OAuthError("The sign-in request expired or could not be verified.") from err
    if payload.get("purpose") != "oauth_state" or payload.get("provider") != expected_provider:
        raise OAuthError("The sign-in request could not be verified.")
    return payload


def authorization_url(provider: OAuthProvider, state: str, nonce: str) -> str:
    if provider == "google":
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": callback_url(provider),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
        }
        return f"{_GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    params = {
        "client_id": settings.apple_oauth_client_id,
        "redirect_uri": callback_url(provider),
        "response_type": "code",
        "response_mode": "form_post",
        "scope": "name email",
        "state": state,
        "nonce": nonce,
    }
    return f"{_APPLE_AUTHORIZE_URL}?{urlencode(params)}"


def _decode_id_token(
    encoded_token: str,
    *,
    jwks_url: str,
    audience: str,
    issuer: str | list[str],
    nonce: str,
    algorithms: list[str],
) -> dict[str, Any]:
    try:
        signing_key = PyJWKClient(jwks_url, timeout=10).get_signing_key_from_jwt(encoded_token)
        claims = jwt.decode(
            encoded_token,
            signing_key.key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except (jwt.PyJWTError, jwt.PyJWKClientError) as err:
        raise OAuthError("The identity provider returned an invalid identity token.") from err
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OAuthError("The identity provider response could not be verified.")
    return claims


def _apple_client_secret() -> str:
    now = datetime.now(UTC)
    private_key = (settings.apple_oauth_private_key or "").replace("\\n", "\n")
    return jwt.encode(
        {
            "iss": settings.apple_oauth_team_id,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "aud": "https://appleid.apple.com",
            "sub": settings.apple_oauth_client_id,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_oauth_key_id},
    )


def exchange_code(
    provider: OAuthProvider, code: str, nonce: str, *, apple_full_name: str | None = None
) -> OAuthProfile:
    if provider == "google":
        token_payload = {
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri": callback_url(provider),
            "grant_type": "authorization_code",
        }
        jwks_url = _GOOGLE_JWKS_URL
        audience = settings.google_oauth_client_id or ""
        issuer: str | list[str] = ["https://accounts.google.com", "accounts.google.com"]
        algorithms = ["RS256"]
    else:
        try:
            client_secret = _apple_client_secret()
        except (jwt.PyJWTError, TypeError, ValueError) as err:
            raise OAuthError("Apple sign-in credentials are invalid.") from err
        token_payload = {
            "code": code,
            "client_id": settings.apple_oauth_client_id,
            "client_secret": client_secret,
            "redirect_uri": callback_url(provider),
            "grant_type": "authorization_code",
        }
        jwks_url = _APPLE_JWKS_URL
        audience = settings.apple_oauth_client_id or ""
        issuer = "https://appleid.apple.com"
        algorithms = ["RS256"]

    try:
        response = httpx.post(
            _GOOGLE_TOKEN_URL if provider == "google" else _APPLE_TOKEN_URL,
            data=token_payload,
            timeout=10,
        )
        response.raise_for_status()
        response_data = response.json()
        id_token = response_data.get("id_token") if isinstance(response_data, dict) else None
    except (httpx.HTTPError, ValueError) as err:
        raise OAuthError("The identity provider could not complete sign-in.") from err
    if not isinstance(id_token, str):
        raise OAuthError("The identity provider did not return an identity token.")

    claims = _decode_id_token(
        id_token,
        jwks_url=jwks_url,
        audience=audience,
        issuer=issuer,
        nonce=nonce,
        algorithms=algorithms,
    )
    email = claims.get("email")
    email_verified = claims.get("email_verified")
    if not isinstance(email, str) or email_verified not in (True, "true"):
        raise OAuthError("The identity provider did not supply a verified email address.")
    name = claims.get("name") if provider == "google" else apple_full_name
    return OAuthProfile(
        provider=provider,
        subject=str(claims["sub"]),
        email=email.lower(),
        full_name=name.strip() if isinstance(name, str) and name.strip() else None,
    )
