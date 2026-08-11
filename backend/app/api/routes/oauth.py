import json
import secrets
import uuid
from typing import Literal
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.rate_limit import enforce_registration_rate_limit
from app.core.security import create_access_token, hash_password
from app.database import get_db
from app.models.notification import NotificationType
from app.models.oauth_identity import OAuthIdentity
from app.models.user import RoleEnum, User
from app.services.audit import record_audit_log
from app.services.notifications import notify
from app.services.oauth import (
    OAuthError,
    OAuthProfile,
    OAuthProvider,
    authorization_url,
    create_state,
    decode_state,
    exchange_code,
    provider_is_configured,
)
from app.services.users import active_user_filters

router = APIRouter(prefix="/auth/oauth", tags=["auth"])


def _frontend_callback(
    *, error: str | None = None, token: str | None = None, next_path: str = "/appointments"
) -> str:
    base = f"{settings.oauth_frontend_url.rstrip('/')}/oauth/callback"
    if error:
        return f"{base}?{urlencode({'error': error})}"
    # Access tokens live in the fragment, which browsers do not send in HTTP
    # requests. OAuthCallbackPage consumes and removes it immediately.
    return f"{base}#{urlencode({'token': token or '', 'next': next_path})}"


def _redirect_to_frontend(
    *, error: str | None = None, token: str | None = None, next_path: str = "/appointments"
) -> RedirectResponse:
    # 303 is critical for Apple's form_post callback: unlike the default
    # 307, it changes the callback POST into a GET when entering the SPA.
    return RedirectResponse(
        _frontend_callback(error=error, token=token, next_path=next_path), status_code=303
    )


def _safe_next_path(value: str | None) -> str:
    return (
        value if value and value.startswith("/") and not value.startswith("//") else "/appointments"
    )


@router.get("/providers")
def providers() -> dict[str, bool]:
    return {
        "google": provider_is_configured("google"),
        "apple": provider_is_configured("apple"),
    }


@router.get("/{provider}/start")
def start_oauth(
    provider: OAuthProvider,
    flow: Literal["login", "register"] = Query(),
    role: RoleEnum | None = Query(default=None),
    owner_student_id: uuid.UUID | None = Query(default=None),
    full_name: str | None = Query(default=None, max_length=200),
    next_path: str = Query(default="/appointments", alias="next"),
) -> RedirectResponse:
    if not provider_is_configured(provider):
        label = provider.capitalize()
        return _redirect_to_frontend(error=f"{label} sign-in is not configured.")
    if flow == "register" and role is None:
        return _redirect_to_frontend(error="Choose a role before continuing.")
    if role == RoleEnum.patient and owner_student_id is None:
        return _redirect_to_frontend(error="Choose your student before continuing.")
    if role != RoleEnum.patient:
        owner_student_id = None

    state, nonce = create_state(
        provider,
        flow=flow,
        role=role,
        owner_student_id=owner_student_id,
        full_name=full_name.strip() if full_name else None,
        next_path=_safe_next_path(next_path),
    )
    return RedirectResponse(authorization_url(provider, state, nonce))


def _apple_name(raw_user: str | None) -> str | None:
    if not raw_user:
        return None
    try:
        name = json.loads(raw_user).get("name", {})
    except (json.JSONDecodeError, AttributeError):
        return None
    parts = [name.get("firstName"), name.get("lastName")]
    joined = " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    return joined or None


def _find_or_create_user(
    db: Session,
    request: Request,
    profile: OAuthProfile,
    state: dict,
) -> User:
    identity = db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == profile.provider,
            OAuthIdentity.subject == profile.subject,
        )
    )
    if identity is not None:
        user = db.get(User, identity.user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            raise OAuthError("This account is inactive.")
        return user

    user = db.scalar(select(User).where(User.email == profile.email))
    if user is not None:
        if not user.is_active or user.deleted_at is not None:
            raise OAuthError("This account is inactive.")
    else:
        if state.get("flow") != "register":
            raise OAuthError("No account uses this email. Sign up first.")
        try:
            role = RoleEnum(state["role"])
        except (KeyError, ValueError) as err:
            raise OAuthError("Choose a valid role before signing up.") from err

        owner_student_id = None
        if role == RoleEnum.patient:
            try:
                owner_student_id = uuid.UUID(state["owner_student_id"])
            except (KeyError, TypeError, ValueError) as err:
                raise OAuthError("Choose your student before signing up.") from err
            student = db.scalar(
                select(User).where(
                    User.id == owner_student_id, *active_user_filters(RoleEnum.student)
                )
            )
            if student is None:
                raise OAuthError("The selected student is no longer available.")

        ip = request.client.host if request.client else None
        enforce_registration_rate_limit(db, email=profile.email, ip_address=ip)
        record_audit_log(
            db,
            action="user_register_attempt",
            attempted_identifier=profile.email,
            ip_address=ip,
        )
        db.commit()
        full_name = state.get("full_name") or profile.full_name or profile.email.split("@", 1)[0]
        user = User(
            email=profile.email,
            # A social-only account has no usable local password. Password
            # reset remains available if the owner later wants one.
            hashed_password=hash_password(secrets.token_urlsafe(48)),
            full_name=full_name,
            role=role,
            owner_student_id=owner_student_id,
        )
        try:
            with db.begin_nested():
                db.add(user)
                db.flush()
        except IntegrityError as err:
            raise OAuthError(
                "An account with this email was just created. Try signing in."
            ) from err
        record_audit_log(
            db,
            action="user_register",
            actor_id=user.id,
            target_type="user",
            target_id=user.id,
            ip_address=ip,
        )
        if role == RoleEnum.patient:
            notify(
                db,
                notification_type=NotificationType.patient_registration_request,
                message=(
                    f"{user.full_name} has requested to join your patient list. "
                    "Confirm them to proceed."
                ),
                recipient_id=owner_student_id,
                related_patient_id=user.id,
            )

    db.add(
        OAuthIdentity(
            user_id=user.id,
            provider=profile.provider,
            subject=profile.subject,
        )
    )
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        raise OAuthError("This provider account is already linked.") from err
    return user


def _complete_oauth(
    provider: OAuthProvider,
    *,
    request: Request,
    db: Session,
    code: str | None,
    state_token: str | None,
    provider_error: str | None,
    apple_full_name: str | None = None,
) -> RedirectResponse:
    if provider_error:
        return _redirect_to_frontend(error="Sign-in was cancelled or denied.")
    if not code or not state_token:
        return _redirect_to_frontend(error="The identity provider response was incomplete.")
    try:
        state = decode_state(state_token, provider)
        profile = exchange_code(provider, code, state["nonce"], apple_full_name=apple_full_name)
        user = _find_or_create_user(db, request, profile, state)
        record_audit_log(
            db,
            action="user_oauth_login_success",
            actor_id=user.id,
            attempted_identifier=user.email,
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        token = create_access_token(subject=user.id, role=user.role.value)
        return _redirect_to_frontend(token=token, next_path=_safe_next_path(state.get("next")))
    except OAuthError as err:
        db.rollback()
        return _redirect_to_frontend(error=str(err))
    except HTTPException as err:
        db.rollback()
        detail = (
            err.detail if isinstance(err.detail, str) else "OAuth sign-in could not be completed."
        )
        return _redirect_to_frontend(error=detail)


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _complete_oauth(
        "google", request=request, db=db, code=code, state_token=state, provider_error=error
    )


@router.post("/apple/callback")
async def apple_callback(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    # Apple's web flow uses application/x-www-form-urlencoded form_post.
    # Parsing it directly avoids adding multipart machinery for a body that
    # cannot contain files.
    fields = parse_qs((await request.body()).decode("utf-8"))

    def first(name: str) -> str | None:
        values = fields.get(name)
        return values[0] if values else None

    return _complete_oauth(
        "apple",
        request=request,
        db=db,
        code=first("code"),
        state_token=first("state"),
        provider_error=first("error"),
        apple_full_name=_apple_name(first("user")),
    )
