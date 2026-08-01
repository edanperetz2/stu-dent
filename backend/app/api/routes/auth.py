from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rate_limit import (
    enforce_login_rate_limit,
    enforce_password_reset_rate_limit,
    enforce_registration_rate_limit,
)
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models.notification import NotificationType
from app.models.user import RoleEnum, User
from app.schemas.auth import (
    LoginIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    RegisterIn,
    TokenOut,
)
from app.schemas.user import UserOut, UserSelfUpdate
from app.services.audit import record_audit_log
from app.services.notifications import notify
from app.services.password_reset import confirm_password_reset, request_password_reset
from app.services.users import active_user_filters

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)) -> User:
    ip = _client_ip(request)
    email = payload.email.lower()
    enforce_registration_rate_limit(db, email=email, ip_address=ip)
    # Recorded unconditionally (success or the 409-already-registered path
    # below), under the real email attempted -- so the per-email check
    # above counts every attempt at that address, and the per-IP check
    # counts every attempt from this IP regardless of which email each one
    # named, without bunching different real registrants' own per-email
    # counters together.
    record_audit_log(db, action="user_register_attempt", attempted_identifier=email, ip_address=ip)
    db.commit()

    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    owner_student_id = None
    owner_confirmed_at = None
    if payload.role == RoleEnum.patient:
        student = db.scalar(
            select(User).where(
                User.id == payload.owner_student_id, *active_user_filters(RoleEnum.student)
            )
        )
        if student is None:
            raise HTTPException(
                status_code=422, detail="owner_student_id must reference an active student"
            )
        owner_student_id = student.id
        # Left unconfirmed until the student explicitly confirms this
        # self-registration -- see services/patients.py::require_confirmed_patient.

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        owner_student_id=owner_student_id,
        owner_confirmed_at=owner_confirmed_at,
    )
    db.add(user)
    db.flush()

    record_audit_log(
        db,
        action="user_register",
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        ip_address=_client_ip(request),
    )

    if payload.role == RoleEnum.patient:
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

    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.lower()
    ip = _client_ip(request)

    enforce_login_rate_limit(
        db, identifier=email, ip_address=ip, failure_action="user_login_failure"
    )

    user = db.scalar(select(User).where(User.email == email))
    # Always runs the real (slow) argon2 comparison, against a dummy hash
    # when there's no real one to check -- otherwise a nonexistent email
    # skipped verify_password() entirely and responded measurably faster
    # than a real wrong-password attempt, leaking which emails are
    # registered purely from login response timing.
    password_valid = verify_password(
        payload.password, user.hashed_password if user is not None else DUMMY_PASSWORD_HASH
    )
    role_matches = payload.role is None or (user is not None and user.role == payload.role)
    if user is None or not user.is_active or not password_valid or not role_matches:
        record_audit_log(
            db,
            action="user_login_failure",
            actor_id=user.id if user else None,
            attempted_identifier=email,
            ip_address=ip,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email, password, or role"
        )

    record_audit_log(
        db,
        action="user_login_success",
        actor_id=user.id,
        attempted_identifier=email,
        ip_address=ip,
    )
    db.commit()

    token = create_access_token(subject=user.id, role=user.role.value)
    return TokenOut(access_token=token)


@router.post("/auth/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
def request_password_reset_route(
    payload: PasswordResetRequestIn, request: Request, db: Session = Depends(get_db)
) -> None:
    """Always 204, whether or not `email` matches a real account -- the
    response itself must not reveal which emails are registered.
    """
    email = payload.email.lower()
    ip = _client_ip(request)
    enforce_password_reset_rate_limit(db, email=email, ip_address=ip)
    request_password_reset(db, email=email, ip_address=ip)


@router.post("/auth/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset_route(
    payload: PasswordResetConfirmIn, db: Session = Depends(get_db)
) -> None:
    succeeded = confirm_password_reset(
        db, raw_token=payload.token, new_password=payload.new_password
    )
    if not succeeded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Request a new one.",
        )


def _with_owner_student_name(db: Session, user: User) -> UserOut:
    out = UserOut.model_validate(user)
    if user.owner_student_id is not None:
        owner = db.get(User, user.owner_student_id)
        if owner is not None:
            out.owner_student_name = owner.full_name
    return out


@router.get("/users/me", response_model=UserOut)
def read_current_user(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    return _with_owner_student_name(db, current_user)


@router.patch("/users/me", response_model=UserOut)
def update_current_user(
    payload: UserSelfUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if payload.contact_phone is not None:
        current_user.contact_phone = payload.contact_phone
    if payload.preferred_time_of_day is not None:
        current_user.preferred_time_of_day = payload.preferred_time_of_day

    record_audit_log(
        db,
        action="user_self_update",
        actor_id=current_user.id,
        target_type="user",
        target_id=current_user.id,
    )
    db.commit()
    db.refresh(current_user)
    return _with_owner_student_name(db, current_user)
