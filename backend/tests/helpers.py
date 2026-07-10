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
