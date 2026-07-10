from tests.helpers import auth_header, register_and_login


def _admin_token(client, email="rooms-admin1@example.com"):
    return register_and_login(client, email, role="admin")


def test_admin_can_create_and_list_room(client):
    token = _admin_token(client)
    create_response = client.post(
        "/admin/rooms", json={"name": "Room 101"}, headers=auth_header(token)
    )
    assert create_response.status_code == 201
    assert create_response.json()["is_active"] is True

    list_response = client.get("/admin/rooms", headers=auth_header(token))
    assert list_response.status_code == 200
    assert any(r["name"] == "Room 101" for r in list_response.json())


def test_non_admin_cannot_create_room(client):
    token = register_and_login(client, "rooms-student1@example.com", role="student")
    response = client.post("/admin/rooms", json={"name": "Room 202"}, headers=auth_header(token))
    assert response.status_code == 403


def test_duplicate_room_name_rejected(client):
    token = _admin_token(client, "rooms-admin2@example.com")
    client.post("/admin/rooms", json={"name": "Room 303"}, headers=auth_header(token))
    response = client.post("/admin/rooms", json={"name": "Room 303"}, headers=auth_header(token))
    assert response.status_code == 409


def test_public_room_list_excludes_inactive(client):
    admin_token = _admin_token(client, "rooms-admin3@example.com")
    student_token = register_and_login(client, "rooms-student2@example.com", role="student")

    room_id = client.post(
        "/admin/rooms", json={"name": "Room 404"}, headers=auth_header(admin_token)
    ).json()["id"]

    visible = client.get("/rooms", headers=auth_header(student_token))
    assert any(r["id"] == room_id for r in visible.json())

    client.patch(
        f"/admin/rooms/{room_id}", json={"is_active": False}, headers=auth_header(admin_token)
    )

    hidden = client.get("/rooms", headers=auth_header(student_token))
    assert all(r["id"] != room_id for r in hidden.json())

    still_in_admin_list = client.get("/admin/rooms", headers=auth_header(admin_token))
    assert any(r["id"] == room_id for r in still_in_admin_list.json())


def test_rooms_require_authentication(client):
    assert client.get("/rooms").status_code == 401
    assert client.get("/admin/rooms").status_code == 401


def test_admin_can_create_and_list_equipment(client):
    token = _admin_token(client, "equip-admin1@example.com")
    create_response = client.post(
        "/admin/equipment",
        json={"name": "X-Ray Machine 1", "equipment_type": "xray"},
        headers=auth_header(token),
    )
    assert create_response.status_code == 201

    list_response = client.get("/admin/equipment", headers=auth_header(token))
    assert list_response.status_code == 200
    assert any(e["name"] == "X-Ray Machine 1" for e in list_response.json())


def test_non_admin_cannot_update_equipment(client):
    admin_token = _admin_token(client, "equip-admin2@example.com")
    student_token = register_and_login(client, "equip-student1@example.com", role="student")
    equipment_id = client.post(
        "/admin/equipment", json={"name": "X-Ray Machine 2"}, headers=auth_header(admin_token)
    ).json()["id"]

    response = client.patch(
        f"/admin/equipment/{equipment_id}",
        json={"is_active": False},
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


def test_public_equipment_list_excludes_inactive(client):
    admin_token = _admin_token(client, "equip-admin3@example.com")
    attending_token = register_and_login(client, "equip-attending1@example.com", role="attending")

    equipment_id = client.post(
        "/admin/equipment", json={"name": "X-Ray Machine 3"}, headers=auth_header(admin_token)
    ).json()["id"]

    visible = client.get("/equipment", headers=auth_header(attending_token))
    assert any(e["id"] == equipment_id for e in visible.json())

    client.patch(
        f"/admin/equipment/{equipment_id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )

    hidden = client.get("/equipment", headers=auth_header(attending_token))
    assert all(e["id"] != equipment_id for e in hidden.json())
