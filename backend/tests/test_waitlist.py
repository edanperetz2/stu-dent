from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_default_room,
    create_equipment,
    create_patient,
    create_room,
    register_and_login,
)

START = "2026-09-01T09:00:00+00:00"
END = "2026-09-01T10:00:00+00:00"


def _book(
    client,
    token,
    *,
    patient_id=None,
    attending_id=None,
    room_id=None,
    equipment_id=None,
    start_time=START,
    end_time=END,
):
    body = {"start_time": start_time, "end_time": end_time}
    if patient_id is not None:
        body["patient_id"] = patient_id
        if room_id is None:
            room_id = create_default_room(client)
    if attending_id is not None:
        body["attending_id"] = attending_id
    if room_id is not None:
        body["room_id"] = room_id
    if equipment_id is not None:
        body["equipment_id"] = equipment_id
    return client.post("/appointments", json=body, headers=auth_header(token))


def _wait(
    client,
    token,
    *,
    patient_id=None,
    attending_id=None,
    room_id=None,
    equipment_id=None,
    start_time=START,
    end_time=END,
):
    body = {"start_time": start_time, "end_time": end_time}
    if patient_id is not None:
        body["patient_id"] = patient_id
    if attending_id is not None:
        body["attending_id"] = attending_id
    if room_id is not None:
        body["room_id"] = room_id
    if equipment_id is not None:
        body["equipment_id"] = equipment_id
    return client.post("/waitlist", json=body, headers=auth_header(token))


def _user_id(client, token):
    return client.get("/users/me", headers=auth_header(token)).json()["id"]


def test_join_waitlist_requires_a_real_conflict(client):
    student_token = register_and_login(client, "wl-s1@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = _wait(client, student_token, patient_id=patient_id)
    assert response.status_code == 409


def test_join_waitlist_succeeds_when_attending_is_genuinely_busy(client):
    occupier_token = register_and_login(client, "wl-s1b@example.com", role="student")
    occupier_patient_id = create_patient(client, occupier_token)
    attending_token = register_and_login(client, "wl-a1@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    _book(client, occupier_token, patient_id=occupier_patient_id, attending_id=attending_id)

    student_token = register_and_login(client, "wl-s1c@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = _wait(client, student_token, patient_id=patient_id, attending_id=attending_id)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert body["resolved_at"] is None
    assert body["conflicts"] == [
        {
            "resource_type": "attending",
            "resource_id": attending_id,
            "resource_name": body["attending_name"],
        }
    ]


def test_patient_joins_waitlist_on_their_own_conflicting_booking(client):
    student_token = register_and_login(client, "wl-s2@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "wl-p2@example.com")
    # Real, active hold on the same patient's time -- student-initiated
    # requests are confirmed immediately when there's no attending.
    _book(client, student_token, patient_id=patient_id)

    response = _wait(client, patient_token)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    # Both "student" and "patient" causes actually fired underneath (same
    # student *and* same patient own both requests), but the patient viewer
    # never gets to distinguish "my own conflict" from "my student is busy"
    # -- see redact_conflicts_for_patient -- so this collapses into one
    # generic "patient" cause.
    assert [c["resource_type"] for c in body["conflicts"]] == ["patient"]


def test_get_waitlist_redacts_student_cause_for_patient_viewer_not_for_student(client):
    """The cross-patient "student busy" scenario, but joined and then
    re-fetched via GET (not just the create-time response) -- confirms
    redaction isn't a one-time thing at creation, and that the *student*
    viewing the exact same entry still sees the real cause (they're
    entitled to their own calendar's detail).
    """
    student_token = register_and_login(client, "wl-s19@example.com", role="student")
    other_patient = create_patient(client, student_token, full_name="Other Patient 19")
    requesting_patient_id, requesting_patient_token = create_and_login_patient(
        client, student_token, "wl-p19@example.com", full_name="Requesting Patient 19"
    )

    _book(client, student_token, patient_id=other_patient)
    entry = _wait(client, requesting_patient_token).json()

    # Re-fetch as the patient -- still redacted.
    as_patient = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(requesting_patient_token)
    ).json()
    assert [c["resource_type"] for c in as_patient["conflicts"]] == ["patient"]
    assert as_patient["conflicts"][0]["resource_id"] == requesting_patient_id

    # Same entry, fetched by the treating student -- full, true detail.
    as_student = client.get(f"/waitlist/{entry['id']}", headers=auth_header(student_token)).json()
    assert as_student["conflicts"][0]["resource_type"] == "student"


def test_create_rejects_invalid_attending_role(client):
    student_token = register_and_login(client, "wl-s3@example.com", role="student")
    other_student_token = register_and_login(client, "wl-s3b@example.com", role="student")
    not_attending_id = _user_id(client, other_student_token)
    patient_id = create_patient(client, student_token)

    response = _wait(client, student_token, patient_id=patient_id, attending_id=not_attending_id)
    assert response.status_code == 422


def test_invalid_time_range_rejected(client):
    student_token = register_and_login(client, "wl-s4@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = _wait(client, student_token, patient_id=patient_id, start_time=END, end_time=START)
    assert response.status_code == 422


def test_visibility_scoping(client):
    occupier_token = register_and_login(client, "wl-s5c@example.com", role="student")
    occupier_patient_id = create_patient(client, occupier_token)
    attending_token = register_and_login(client, "wl-a5@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    _book(client, occupier_token, patient_id=occupier_patient_id, attending_id=attending_id)

    student_token = register_and_login(client, "wl-s5@example.com", role="student")
    other_student_token = register_and_login(client, "wl-s5b@example.com", role="student")
    other_attending_token = register_and_login(client, "wl-a5b@example.com", role="attending")
    admin_token = register_and_login(client, "wl-admin5@example.com", role="admin")
    patient_id = create_patient(client, student_token)

    entry = _wait(client, student_token, patient_id=patient_id, attending_id=attending_id).json()

    assert (
        client.get(f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)).status_code
        == 404
    )
    assert (
        client.get(
            f"/waitlist/{entry['id']}", headers=auth_header(other_attending_token)
        ).status_code
        == 404
    )
    assert (
        client.get(f"/waitlist/{entry['id']}", headers=auth_header(student_token)).status_code
        == 200
    )
    assert (
        client.get(f"/waitlist/{entry['id']}", headers=auth_header(attending_token)).status_code
        == 200
    )
    assert (
        client.get(f"/waitlist/{entry['id']}", headers=auth_header(admin_token)).status_code == 200
    )

    listing = client.get("/waitlist", headers=auth_header(other_student_token)).json()
    assert all(e["id"] != entry["id"] for e in listing)


def test_cancel_by_owning_student(client):
    student_token = register_and_login(client, "wl-s6@example.com", role="student")
    occupier_patient_id = create_patient(client, student_token)
    _book(client, student_token, patient_id=occupier_patient_id)

    # Same student, a different patient, same overlapping time -- conflicts
    # on "student" without needing anyone else involved.
    patient_id = create_patient(client, student_token)
    entry = _wait(client, student_token, patient_id=patient_id).json()

    response = client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(student_token))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_by_self_patient(client):
    student_token = register_and_login(client, "wl-s7@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "wl-p7@example.com")
    _book(client, student_token, patient_id=patient_id)

    entry = _wait(client, patient_token).json()

    response = client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(patient_token))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_already_cancelled_conflicts(client):
    student_token = register_and_login(client, "wl-s8@example.com", role="student")
    patient_id = create_patient(client, student_token)
    _book(client, student_token, patient_id=patient_id)
    entry = _wait(client, student_token, patient_id=patient_id).json()

    client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(student_token))
    response = client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(student_token))
    assert response.status_code == 409


def test_admin_cannot_cancel_others_entry(client):
    student_token = register_and_login(client, "wl-s9@example.com", role="student")
    admin_token = register_and_login(client, "wl-admin9@example.com", role="admin")
    patient_id = create_patient(client, student_token)
    _book(client, student_token, patient_id=patient_id)
    entry = _wait(client, student_token, patient_id=patient_id).json()

    response = client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(admin_token))
    assert response.status_code == 403


def test_waitlist_requires_authentication(client):
    assert client.get("/waitlist").status_code == 401
    assert client.post("/waitlist", json={}).status_code == 401


def test_cancellation_promotes_student_originated_entry_to_awaiting_confirmation(client):
    student_token = register_and_login(client, "wl-s10@example.com", role="student")
    attending_token = register_and_login(client, "wl-a10@example.com", role="attending")
    attending_id = _user_id(client, attending_token)

    other_student_token = register_and_login(client, "wl-s10b@example.com", role="student")
    _, waiting_patient_token = create_and_login_patient(
        client, other_student_token, "wl-p10b@example.com"
    )
    waiting_patient_id = _user_id(client, waiting_patient_token)

    patient_id = create_patient(client, student_token)
    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()

    entry = _wait(
        client, other_student_token, patient_id=waiting_patient_id, attending_id=attending_id
    ).json()
    assert entry["status"] == "active"

    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "booked"
    assert updated_entry["resolved_at"] is not None
    assert updated_entry["resulting_appointment_id"] is not None
    # Student-originated (student_confirmed_at was captured at join time) +
    # an attending assigned but not yet approved -> awaiting_confirmation,
    # exactly as recompute_status would derive for a fresh booking.
    assert updated_entry["resulting_appointment_status"] == "awaiting_confirmation"

    resulting = client.get(
        f"/appointments/{updated_entry['resulting_appointment_id']}",
        headers=auth_header(other_student_token),
    ).json()
    assert resulting["student_id"] == _user_id(client, other_student_token)
    assert resulting["attending_id"] == attending_id
    assert resulting["status"] == "awaiting_confirmation"

    student_notifications = client.get(
        "/notifications", headers=auth_header(other_student_token)
    ).json()
    assert any(n["notification_type"] == "waitlist_slot_available" for n in student_notifications)

    patient_notifications = client.get(
        "/notifications", headers=auth_header(waiting_patient_token)
    ).json()
    assert any(n["notification_type"] == "waitlist_slot_available" for n in patient_notifications)

    # The attending is now responsible for approving a brand-new
    # appointment they never asked for -- they must be told, same as the
    # student and patient.
    attending_notifications = client.get(
        "/notifications", headers=auth_header(attending_token)
    ).json()
    assert any(n["notification_type"] == "waitlist_slot_available" for n in attending_notifications)


def test_cancellation_promotes_patient_originated_entry_to_proposed(client):
    student_token = register_and_login(client, "wl-s11@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "wl-p11@example.com"
    )

    # The owning student books a real, immediately-confirmed slot for the
    # patient, so the patient's own overlapping request genuinely conflicts.
    appointment = _book(client, student_token, patient_id=patient_id).json()

    entry = _wait(client, patient_token).json()
    assert entry["status"] == "active"

    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(patient_token)
    ).json()
    assert updated_entry["status"] == "booked"
    # Patient-originated -- no student_confirmed_at was ever captured, so
    # the promoted appointment lands in "proposed", not a fabricated
    # confirmation nobody actually gave.
    assert updated_entry["resulting_appointment_status"] == "proposed"


def test_reject_also_triggers_promotion(client):
    student_token = register_and_login(client, "wl-s12@example.com", role="student")
    attending_token = register_and_login(client, "wl-a12@example.com", role="attending")
    attending_id = _user_id(client, attending_token)

    other_student_token = register_and_login(client, "wl-s12b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)

    patient_id = create_patient(client, student_token)
    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()

    entry = _wait(
        client, other_student_token, patient_id=other_patient_id, attending_id=attending_id
    ).json()

    client.post(f"/appointments/{appointment['id']}/reject", headers=auth_header(attending_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "booked"


def test_unrelated_cancellation_does_not_touch_entry(client):
    student_token = register_and_login(client, "wl-s13@example.com", role="student")
    admin_token = register_and_login(client, "wl-admin13@example.com", role="admin")
    room_id = create_room(client, admin_token, "WL Room 13")

    occupier_token = register_and_login(client, "wl-s13c@example.com", role="student")
    occupier_patient_id = create_patient(client, occupier_token)
    _book(client, occupier_token, patient_id=occupier_patient_id, room_id=room_id)

    other_student_token = register_and_login(client, "wl-s13b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)
    entry = _wait(client, other_student_token, patient_id=other_patient_id, room_id=room_id).json()

    patient_id = create_patient(client, student_token)
    appointment = _book(client, student_token, patient_id=patient_id).json()
    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "active"


def test_non_overlapping_time_does_not_match(client):
    student_token = register_and_login(client, "wl-s15@example.com", role="student")
    admin_token = register_and_login(client, "wl-admin15@example.com", role="admin")
    equipment_id = create_equipment(client, admin_token, "WL Equipment 15")

    occupier_token = register_and_login(client, "wl-s15c@example.com", role="student")
    occupier_patient_id = create_patient(client, occupier_token)
    _book(
        client,
        occupier_token,
        patient_id=occupier_patient_id,
        equipment_id=equipment_id,
        start_time="2026-09-02T09:00:00+00:00",
        end_time="2026-09-02T10:00:00+00:00",
    )

    other_student_token = register_and_login(client, "wl-s15b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)
    entry = _wait(
        client,
        other_student_token,
        patient_id=other_patient_id,
        equipment_id=equipment_id,
        start_time="2026-09-02T09:00:00+00:00",
        end_time="2026-09-02T10:00:00+00:00",
    ).json()

    patient_id = create_patient(client, student_token)
    appointment = _book(
        client, student_token, patient_id=patient_id, equipment_id=equipment_id
    ).json()
    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "active"


def test_multi_cause_entry_not_resolved_until_every_cause_clears(client):
    admin_token = register_and_login(client, "wl-admin16@example.com", role="admin")
    room_id = create_room(client, admin_token, "WL Room 16")
    attending_token = register_and_login(client, "wl-a16@example.com", role="attending")
    attending_id = _user_id(client, attending_token)

    # Two independent occupiers: one holds the attending, the other holds
    # the room, over the same window -- the waiter's request conflicts on
    # both, so clearing just one must not be enough to promote it.
    occupier_a_token = register_and_login(client, "wl-s16a@example.com", role="student")
    occupier_a_patient_id = create_patient(client, occupier_a_token)
    appointment_a = _book(
        client, occupier_a_token, patient_id=occupier_a_patient_id, attending_id=attending_id
    ).json()

    occupier_b_token = register_and_login(client, "wl-s16b@example.com", role="student")
    occupier_b_patient_id = create_patient(client, occupier_b_token)
    appointment_b = _book(
        client, occupier_b_token, patient_id=occupier_b_patient_id, room_id=room_id
    ).json()

    waiter_token = register_and_login(client, "wl-s16c@example.com", role="student")
    waiter_patient_id = create_patient(client, waiter_token)
    entry = _wait(
        client,
        waiter_token,
        patient_id=waiter_patient_id,
        attending_id=attending_id,
        room_id=room_id,
    ).json()
    assert sorted(c["resource_type"] for c in entry["conflicts"]) == ["attending", "room"]

    # Freeing only the attending isn't enough -- the room is still held.
    client.post(
        f"/appointments/{appointment_a['id']}/cancel", headers=auth_header(occupier_a_token)
    )
    still_active = client.get(f"/waitlist/{entry['id']}", headers=auth_header(waiter_token)).json()
    assert still_active["status"] == "active"

    # Freeing the room too clears every recorded cause -- now it promotes.
    client.post(
        f"/appointments/{appointment_b['id']}/cancel", headers=auth_header(occupier_b_token)
    )
    resolved = client.get(f"/waitlist/{entry['id']}", headers=auth_header(waiter_token)).json()
    assert resolved["status"] == "booked"


def test_stale_conflict_cause_does_not_block_recheck_on_a_different_resource(client):
    # Regression test for a real bug: the recheck used to gate on the
    # entry's *original* conflict_resource_types (captured once at
    # creation, never updated), so once the true current blocker had
    # shifted to a resource that wasn't part of that original cause list,
    # a cancellation that freed it was silently ignored forever.
    admin_token = register_and_login(client, "wl-admin18@example.com", role="admin")
    room_id = create_room(client, admin_token, "WL Room 18")
    attending_token = register_and_login(client, "wl-a18@example.com", role="attending")
    attending_id = _user_id(client, attending_token)

    occupier_a_token = register_and_login(client, "wl-s18a@example.com", role="student")
    occupier_a_patient_id = create_patient(client, occupier_a_token)
    appointment_a = _book(
        client,
        occupier_a_token,
        patient_id=occupier_a_patient_id,
        attending_id=attending_id,
        start_time="2026-09-03T09:00:00+00:00",
        end_time="2026-09-03T10:00:00+00:00",
    ).json()

    waiter_token = register_and_login(client, "wl-s18c@example.com", role="student")
    waiter_patient_id = create_patient(client, waiter_token)
    entry = _wait(
        client,
        waiter_token,
        patient_id=waiter_patient_id,
        attending_id=attending_id,
        room_id=room_id,
        start_time="2026-09-03T09:00:00+00:00",
        end_time="2026-09-03T10:00:00+00:00",
    ).json()
    # Room is free at creation time -- the only real conflict is the
    # attending.
    assert [c["resource_type"] for c in entry["conflicts"]] == ["attending"]
    assert entry["conflicts"][0]["resource_id"] == attending_id

    # A second, unrelated booking now takes the room -- something the
    # entry's stale conflict_resource_types (still just ["attending"])
    # doesn't know about.
    occupier_b_token = register_and_login(client, "wl-s18b@example.com", role="student")
    occupier_b_patient_id = create_patient(client, occupier_b_token)
    appointment_b = _book(
        client,
        occupier_b_token,
        patient_id=occupier_b_patient_id,
        room_id=room_id,
        start_time="2026-09-03T09:00:00+00:00",
        end_time="2026-09-03T10:00:00+00:00",
    ).json()

    # Freeing the attending isn't enough -- the room is still held by the
    # second booking, so this must correctly stay active.
    client.post(
        f"/appointments/{appointment_a['id']}/cancel", headers=auth_header(occupier_a_token)
    )
    still_active = client.get(f"/waitlist/{entry['id']}", headers=auth_header(waiter_token)).json()
    assert still_active["status"] == "active"

    # Freeing the room -- a resource never present in the entry's original
    # conflict_resource_types -- must still trigger a real recheck and
    # promote the entry, not be silently skipped.
    client.post(
        f"/appointments/{appointment_b['id']}/cancel", headers=auth_header(occupier_b_token)
    )
    resolved = client.get(f"/waitlist/{entry['id']}", headers=auth_header(waiter_token)).json()
    assert resolved["status"] == "booked"


def test_rescheduling_appointment_away_promotes_waitlist_entry_for_freed_room(client):
    # Regression test: moving an appointment to a different room (without
    # ever cancelling it) used to never trigger a waitlist recheck, only
    # cancel/reject/expiry did -- so a genuinely-freed room left a waiting
    # entry stranded.
    admin_token = register_and_login(client, "wl-admin19@example.com", role="admin")
    room_id = create_room(client, admin_token, "WL Room 19a")
    other_room_id = create_room(client, admin_token, "WL Room 19b")

    occupier_token = register_and_login(client, "wl-s19a@example.com", role="student")
    occupier_patient_id = create_patient(client, occupier_token)
    appointment = _book(
        client,
        occupier_token,
        patient_id=occupier_patient_id,
        room_id=room_id,
        start_time="2026-09-04T09:00:00+00:00",
        end_time="2026-09-04T10:00:00+00:00",
    ).json()

    waiter_token = register_and_login(client, "wl-s19b@example.com", role="student")
    waiter_patient_id = create_patient(client, waiter_token)
    entry = _wait(
        client,
        waiter_token,
        patient_id=waiter_patient_id,
        room_id=room_id,
        start_time="2026-09-04T09:00:00+00:00",
        end_time="2026-09-04T10:00:00+00:00",
    ).json()
    assert entry["conflicts"][0]["resource_type"] == "room"

    # Move the occupying appointment to a different room at the same time
    # -- nothing was cancelled, but Room 19a is now genuinely free.
    update_response = client.patch(
        f"/appointments/{appointment['id']}",
        json={"room_id": other_room_id},
        headers=auth_header(occupier_token),
    )
    assert update_response.status_code == 200

    resolved = client.get(f"/waitlist/{entry['id']}", headers=auth_header(waiter_token)).json()
    assert resolved["status"] == "booked"
    assert resolved["resulting_appointment_id"] is not None


def test_competing_entries_for_the_same_freed_slot_first_created_wins(client):
    attending_token = register_and_login(client, "wl-a17@example.com", role="attending")
    attending_id = _user_id(client, attending_token)

    occupier_token = register_and_login(client, "wl-s17c@example.com", role="student")
    occupier_patient_id = create_patient(client, occupier_token)
    appointment = _book(
        client, occupier_token, patient_id=occupier_patient_id, attending_id=attending_id
    ).json()

    waiter1_token = register_and_login(client, "wl-s17a@example.com", role="student")
    waiter1_patient_id = create_patient(client, waiter1_token)
    entry1 = _wait(
        client, waiter1_token, patient_id=waiter1_patient_id, attending_id=attending_id
    ).json()

    waiter2_token = register_and_login(client, "wl-s17b@example.com", role="student")
    waiter2_patient_id = create_patient(client, waiter2_token)
    entry2 = _wait(
        client, waiter2_token, patient_id=waiter2_patient_id, attending_id=attending_id
    ).json()

    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(occupier_token))

    updated1 = client.get(f"/waitlist/{entry1['id']}", headers=auth_header(waiter1_token)).json()
    updated2 = client.get(f"/waitlist/{entry2['id']}", headers=auth_header(waiter2_token)).json()
    # Deterministic, not just "exactly one" -- entry1 was created first, so
    # it's always the one promoted; entry2 stays active for the next
    # opportunity rather than being left to arbitrary DB row order.
    assert updated1["status"] == "booked"
    assert updated2["status"] == "active"


def test_losing_entry_keeps_priority_over_newer_entries_next_round(client):
    """entry_c loses the first round to entry_b (created earlier). A
    second, newer entry_d joins afterward wanting the same thing. When the
    slot frees up again, entry_c -- not entry_d -- must win: having lost
    once doesn't push it behind entries created after it.
    """
    attending_token = register_and_login(client, "wl-a18@example.com", role="attending")
    attending_id = _user_id(client, attending_token)

    occupier_token = register_and_login(client, "wl-s18occ@example.com", role="student")
    occupier_patient_id = create_patient(client, occupier_token)
    appointment = _book(
        client, occupier_token, patient_id=occupier_patient_id, attending_id=attending_id
    ).json()

    student_b_token = register_and_login(client, "wl-s18b@example.com", role="student")
    patient_b_id = create_patient(client, student_b_token)
    entry_b = _wait(
        client, student_b_token, patient_id=patient_b_id, attending_id=attending_id
    ).json()

    student_c_token = register_and_login(client, "wl-s18c@example.com", role="student")
    patient_c_id = create_patient(client, student_c_token)
    entry_c = _wait(
        client, student_c_token, patient_id=patient_c_id, attending_id=attending_id
    ).json()

    # Round 1: only b and c are waiting -- b (created first) wins.
    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(occupier_token))
    round1_b = client.get(f"/waitlist/{entry_b['id']}", headers=auth_header(student_b_token)).json()
    round1_c = client.get(f"/waitlist/{entry_c['id']}", headers=auth_header(student_c_token)).json()
    assert round1_b["status"] == "booked"
    assert round1_c["status"] == "active"

    # d joins after c lost, wanting the same slot.
    student_d_token = register_and_login(client, "wl-s18d@example.com", role="student")
    patient_d_id = create_patient(client, student_d_token)
    entry_d = _wait(
        client, student_d_token, patient_id=patient_d_id, attending_id=attending_id
    ).json()

    # Round 2: free the slot b just took -- c (older) must win over d
    # (newer), even though c already lost once.
    client.post(
        f"/appointments/{round1_b['resulting_appointment_id']}/cancel",
        headers=auth_header(student_b_token),
    )
    round2_c = client.get(f"/waitlist/{entry_c['id']}", headers=auth_header(student_c_token)).json()
    round2_d = client.get(f"/waitlist/{entry_d['id']}", headers=auth_header(student_d_token)).json()
    assert round2_c["status"] == "booked"
    assert round2_d["status"] == "active"
