def register(
    client,
    email,
    password="password123",
    role="student",
    full_name="Test User",
):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "role": role},
    )


def login(client, email, password="password123"):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(
    client, email, role="student", password="password123", full_name="Test User"
):
    register(client, email, password=password, role=role, full_name=full_name)
    return login(client, email, password=password).json()["access_token"]


def create_patient(client, student_token, full_name="Test Patient", contact_phone=None):
    response = client.post(
        "/patients",
        json={"full_name": full_name, "contact_phone": contact_phone},
        headers=auth_header(student_token),
    )
    return response.json()["id"]


def set_patient_credentials(client, student_token, patient_id, email, password="password123"):
    return client.post(
        f"/patients/{patient_id}/credentials",
        json={"email": email, "password": password},
        headers=auth_header(student_token),
    )


def patient_login(client, email, password="password123"):
    return client.post("/patients/login", json={"email": email, "password": password})


def create_and_login_patient(
    client, student_token, email, full_name="Test Patient", password="password123"
):
    patient_id = create_patient(client, student_token, full_name=full_name)
    set_patient_credentials(client, student_token, patient_id, email, password=password)
    token = patient_login(client, email, password=password).json()["access_token"]
    return patient_id, token


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
