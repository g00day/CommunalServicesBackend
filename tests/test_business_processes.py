async def test_bp_registration_activation_and_login(client, test_helpers):
    register_response = await client.post(
        "/api/auth/register",
        json={
            "email": "bp-user@example.com",
            "password": "Password123!",
            "name": "Мария",
            "surname": "Смирнова",
        },
    )
    assert register_response.status_code == 201

    activate_response = await client.get(
        "/api/auth/confirm-email",
        params={"token": test_helpers.email_confirm_token("bp-user@example.com")},
    )
    assert activate_response.status_code == 200

    login_response = await client.post(
        "/api/auth/login",
        json={"email": "bp-user@example.com", "password": "Password123!"},
    )
    assert login_response.status_code == 200


async def test_bp_create_ticket_and_view_in_list_and_card(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="bp-owner@example.com")
    headers = await test_helpers.auth_headers(client, "bp-owner@example.com")
    address_id = await test_helpers.first_address_id(db_session)

    created = await test_helpers.create_ticket(client, headers, address_id, title="Нет воды")
    list_response = await client.get("/api/tickets", headers=headers)
    detail_response = await client.get(f"/api/tickets/{created['id']}", headers=headers)

    assert list_response.status_code == 200
    assert any(item["id"] == created["id"] for item in list_response.json())
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == created["id"]


async def test_bp_user_closes_own_ticket(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="bp-closer@example.com")
    headers = await test_helpers.auth_headers(client, "bp-closer@example.com")
    address_id = await test_helpers.first_address_id(db_session)

    created = await test_helpers.create_ticket(client, headers, address_id, title="Сломан кран")
    close_response = await client.patch(f"/api/tickets/{created['id']}/close", headers=headers)

    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"
    assert close_response.json()["is_closed"] is True


async def test_bp_staff_processes_ticket_to_completed(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="bp-citizen@example.com")
    await test_helpers.create_user(db_session, email="bp-manager@example.com", role_id=2)
    citizen_headers = await test_helpers.auth_headers(client, "bp-citizen@example.com")
    manager_headers = await test_helpers.auth_headers(client, "bp-manager@example.com")
    address_id = await test_helpers.first_address_id(db_session)

    created = await test_helpers.create_ticket(client, citizen_headers, address_id, title="Сломан лифт")
    accepted = await client.patch(
        f"/api/tickets/{created['id']}/status",
        headers=manager_headers,
        json={"status_code": "accepted"},
    )
    completed = await client.patch(
        f"/api/tickets/{created['id']}/status",
        headers=manager_headers,
        json={"status_code": "completed"},
    )

    assert accepted.status_code == 200
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["is_closed"] is True


async def test_bp_add_chat_participant_and_exchange_message(client, db_session, test_helpers):
    owner = await test_helpers.create_user(db_session, email="bp-owner-chat@example.com")
    manager = await test_helpers.create_user(db_session, email="bp-manager-chat@example.com", role_id=2)
    participant = await test_helpers.create_user(db_session, email="bp-participant-chat@example.com")
    owner_headers = await test_helpers.auth_headers(client, owner.email)
    manager_headers = await test_helpers.auth_headers(client, manager.email)
    participant_headers = await test_helpers.auth_headers(client, participant.email)
    address_id = await test_helpers.first_address_id(db_session)

    created = await test_helpers.create_ticket(client, owner_headers, address_id, title="Чат по заявке")
    add_participant_response = await client.post(
        f"/api/tickets/{created['id']}/participants",
        headers=manager_headers,
        json={"user_id": participant.id, "role_in_chat": "executor"},
    )
    message_response = await client.post(
        f"/api/tickets/{created['id']}/messages",
        headers=participant_headers,
        data={"text": "Принял заявку в работу"},
    )
    history_response = await client.get(f"/api/tickets/{created['id']}/messages", headers=owner_headers)

    assert add_participant_response.status_code == 201
    assert message_response.status_code == 201
    assert history_response.status_code == 200
    assert any(item["text"] == "Принял заявку в работу" for item in history_response.json())
