from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rate_limit import enforce_login_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.notification import NotificationType
from app.models.user import RoleEnum, User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut
from app.schemas.user import UserOut, UserSelfUpdate
from app.services.audit import record_audit_log
from app.services.notifications import notify
from app.services.users import active_user_filters

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)) -> User:
    email = payload.email.lower()
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
        )

    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.lower()
    ip = _client_ip(request)

    enforce_login_rate_limit(db, identifier=email, failure_action="user_login_failure")

    user = db.scalar(select(User).where(User.email == email))
    role_matches = payload.role is None or (user is not None and user.role == payload.role)
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.hashed_password)
        or not role_matches
    ):
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
