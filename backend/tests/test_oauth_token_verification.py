import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services import oauth as oauth_service
from app.services.oauth import OAuthError

# Every other OAuth test mocks exchange_code() wholesale, so none of them
# ever run the real RS256 signature verification, audience/issuer/expiry
# checks, or nonce-replay check inside _decode_id_token -- the actual
# security-critical part of the whole flow. These tests sign real tokens
# with a real generated RSA keypair and only stub the network JWKS *fetch*
# (PyJWKClient's HTTP call), so jwt.decode()'s real cryptographic
# verification genuinely runs against real, unmocked signatures.

AUDIENCE = "test-client-id"
ISSUER = ["https://accounts.google.com", "accounts.google.com"]


@pytest.fixture
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _sign_token(private_key, claims):
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key-1"})


def _base_claims(nonce, **overrides):
    now = datetime.now(UTC)
    claims = {
        "iss": "https://accounts.google.com",
        "aud": AUDIENCE,
        "sub": "google-subject-123",
        "email": "user@example.com",
        "email_verified": True,
        "nonce": nonce,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return claims


def _stub_jwks_client(monkeypatch, public_key):
    class _StubSigningKey:
        def __init__(self, key):
            self.key = key

    class _StubJWKClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_signing_key_from_jwt(self, token):
            return _StubSigningKey(public_key)

    monkeypatch.setattr(oauth_service, "PyJWKClient", _StubJWKClient)


def _decode(token, *, nonce):
    return oauth_service._decode_id_token(
        token,
        jwks_url="https://example.com/jwks",
        audience=AUDIENCE,
        issuer=ISSUER,
        nonce=nonce,
        algorithms=["RS256"],
    )


def test_accepts_a_genuinely_valid_signed_token(monkeypatch, keypair):
    private_key, public_key = keypair
    _stub_jwks_client(monkeypatch, public_key)
    nonce = secrets.token_urlsafe(16)

    claims = _decode(_sign_token(private_key, _base_claims(nonce)), nonce=nonce)

    assert claims["sub"] == "google-subject-123"
    assert claims["email"] == "user@example.com"


def test_rejects_a_token_signed_by_a_different_key(monkeypatch, keypair):
    # The signature was produced by a DIFFERENT private key than the one
    # the (stubbed) JWKS document vouches for -- a forged/tampered token.
    # If this didn't raise, _decode_id_token would accept any signature.
    _, real_public_key = keypair
    forged_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _stub_jwks_client(monkeypatch, real_public_key)
    nonce = secrets.token_urlsafe(16)

    with pytest.raises(OAuthError):
        _decode(_sign_token(forged_private_key, _base_claims(nonce)), nonce=nonce)


def test_rejects_an_expired_token(monkeypatch, keypair):
    private_key, public_key = keypair
    _stub_jwks_client(monkeypatch, public_key)
    nonce = secrets.token_urlsafe(16)
    now = datetime.now(UTC)
    claims = _base_claims(nonce, iat=now - timedelta(minutes=10), exp=now - timedelta(minutes=5))

    with pytest.raises(OAuthError):
        _decode(_sign_token(private_key, claims), nonce=nonce)


def test_rejects_a_token_with_the_wrong_audience(monkeypatch, keypair):
    private_key, public_key = keypair
    _stub_jwks_client(monkeypatch, public_key)
    nonce = secrets.token_urlsafe(16)
    claims = _base_claims(nonce, aud="someone-elses-client-id")

    with pytest.raises(OAuthError):
        _decode(_sign_token(private_key, claims), nonce=nonce)


def test_rejects_a_token_with_the_wrong_issuer(monkeypatch, keypair):
    private_key, public_key = keypair
    _stub_jwks_client(monkeypatch, public_key)
    nonce = secrets.token_urlsafe(16)
    claims = _base_claims(nonce, iss="https://evil.example.com")

    with pytest.raises(OAuthError):
        _decode(_sign_token(private_key, claims), nonce=nonce)


def test_rejects_a_nonce_that_does_not_match_the_expected_value(monkeypatch, keypair):
    # A genuinely valid, correctly-signed, non-expired token -- but for a
    # nonce that doesn't match what this server actually issued. Proves the
    # replay-protection check runs independently of signature validity.
    private_key, public_key = keypair
    _stub_jwks_client(monkeypatch, public_key)
    token = _sign_token(private_key, _base_claims("nonce-the-server-issued"))

    with pytest.raises(OAuthError):
        _decode(token, nonce="a-completely-different-nonce")
