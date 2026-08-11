import uuid
from datetime import UTC, datetime, time, timedelta


def relative_datetime(*, days: int = 30, hour: int = 9, minute: int = 0) -> datetime:
    """Return a stable UTC wall-clock time relative to the test run.

    Integration tests should describe whether a timestamp is in the past or
    future, not silently expire when the calendar catches up with fixture
    data. Normalizing to a whole minute keeps API assertions readable and
    deterministic within one test run.
    """
    target_date = (datetime.now(UTC) + timedelta(days=days)).date()
    return datetime.combine(target_date, time(hour=hour, minute=minute), tzinfo=UTC)


def relative_iso(*, days: int = 30, hour: int = 9, minute: int = 0) -> str:
    return relative_datetime(days=days, hour=hour, minute=minute).isoformat()


def relative_slot(
    *, days: int = 30, hour: int = 9, minute: int = 0, duration_minutes: int = 60
) -> tuple[str, str]:
    start = relative_datetime(days=days, hour=hour, minute=minute)
    return start.isoformat(), (start + timedelta(minutes=duration_minutes)).isoformat()


def register(
    client,
    email,
    password="password123",
    role="student",
    full_name="Test User",
    owner_student_id=None,
):
    payload = {"email": email, "password": password, "full_name": full_name, "role": role}
    if owner_student_id is not None:
        payload["owner_student_id"] = str(owner_student_id)
    return client.post("/auth/register", json=payload)


def login(client, email, password="password123", role=None):
    payload = {"email": email, "password": password}
    if role is not None:
        payload["role"] = role
    return client.post("/auth/login", json=payload)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(
    client, email, role="student", password="password123", full_name="Test User"
):
    register(client, email, password=password, role=role, full_name=full_name)
    return login(client, email, password=password).json()["access_token"]


def create_patient(
    client,
    student_token,
    full_name="Test Patient",
    email=None,
    password="password123",
    contact_phone=None,
):
    """Student-initiated creation -- auto-confirmed immediately."""
    if email is None:
        email = f"patient-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/patients",
        json={
            "full_name": full_name,
            "email": email,
            "password": password,
            "contact_phone": contact_phone,
        },
        headers=auth_header(student_token),
    )
    return response.json()["id"]


def create_and_login_patient(
    client, student_token, email, full_name="Test Patient", password="password123"
):
    patient_id = create_patient(
        client, student_token, full_name=full_name, email=email, password=password
    )
    token = login(client, email, password=password).json()["access_token"]
    return patient_id, token


def register_patient(
    client, owner_student_id, email, full_name="Test Patient", password="password123"
):
    """Patient self-registration -- pending until the owning student confirms."""
    register(
        client,
        email,
        password=password,
        role="patient",
        full_name=full_name,
        owner_student_id=owner_student_id,
    )
    return login(client, email, password=password).json()["access_token"]


def confirm_patient(client, student_token, patient_id):
    return client.post(f"/patients/{patient_id}/confirm", headers=auth_header(student_token))


def create_room(client, admin_token, name="Room A"):
    return client.post(
        "/admin/rooms", json={"name": name}, headers=auth_header(admin_token)
    ).json()["id"]


def create_equipment(client, admin_token, name="Equip A", equipment_type=None):
    return client.post(
        "/admin/equipment",
        json={"name": name, "equipment_type": equipment_type},
        headers=auth_header(admin_token),
    ).json()["id"]


def create_default_room(client) -> str:
    """A throwaway admin + room, for tests that need *some* valid room for a
    student-initiated booking (now required) but don't care which one."""
    admin_token = register_and_login(
        client, f"auto-room-admin-{uuid.uuid4().hex}@example.com", role="admin"
    )
    return create_room(client, admin_token, f"Auto Room {uuid.uuid4().hex}")
