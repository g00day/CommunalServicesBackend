from sqlalchemy import select

from app.models import User


async def test_server_register_user_creates_inactive_account(client, db_session):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "new-user@example.com",
            "password": "Password123!",
            "name": "Иван",
            "surname": "Петров",
        },
    )

    assert response.status_code == 201
    result = await db_session.execute(select(User).where(User.email == "new-user@example.com"))
    assert result.scalar_one().is_activated is False


async def test_server_register_rejects_duplicate_email(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="duplicate@example.com")

    response = await client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "Password123!",
            "name": "Иван",
            "surname": "Петров",
        },
    )

    assert response.status_code == 409


async def test_server_login_rejects_not_activated_user(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="inactive@example.com", is_activated=False)

    response = await client.post(
        "/api/auth/login",
        json={
            "email": "inactive@example.com", 
            "password": "Password123!"
        },
    )

    assert response.status_code == 403


async def test_server_login_returns_tokens_for_activated_user(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="active@example.com")

    response = await client.post(
        "/api/auth/login",
        json={
            "email": "active@example.com",
            "password": "Password123!"
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


async def test_server_me_returns_current_user_profile(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="profile@example.com")
    headers = await test_helpers.auth_headers(client, "profile@example.com")

    response = await client.get("/api/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "profile@example.com"


async def test_server_create_ticket_returns_created_status(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="creator@example.com")
    headers = await test_helpers.auth_headers(client, "creator@example.com")
    address_id = await test_helpers.first_address_id(db_session)

    response = await client.post(
        "/api/tickets",
        headers=headers,
        data={
            "title": "Прорыв трубы",
            "description": "Течет стояк",
            "address_id": str(address_id)
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "created"


async def test_server_get_tickets_returns_own_tickets(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="owner@example.com")
    headers = await test_helpers.auth_headers(client, "owner@example.com")
    address_id = await test_helpers.first_address_id(db_session)

    created = await test_helpers.create_ticket(client, headers, address_id, title="Моя заявка")
    response = await client.get("/api/tickets", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["id"] == created["id"]


async def test_server_get_ticket_denies_foreign_user(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="ticket-owner@example.com")
    await test_helpers.create_user(db_session, email="stranger@example.com")
    owner_headers = await test_helpers.auth_headers(client, "ticket-owner@example.com")
    stranger_headers = await test_helpers.auth_headers(client, "stranger@example.com")
    address_id = await test_helpers.first_address_id(db_session)

    ticket = await test_helpers.create_ticket(client, owner_headers, address_id)
    response = await client.get(f"/api/tickets/{ticket['id']}", headers=stranger_headers)

    assert response.status_code == 403


async def test_server_manager_can_update_ticket_status(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="ticket-owner2@example.com")
    await test_helpers.create_user(db_session, email="manager@example.com", role_id=2)
    owner_headers = await test_helpers.auth_headers(client, "ticket-owner2@example.com")
    manager_headers = await test_helpers.auth_headers(client, "manager@example.com")
    address_id = await test_helpers.first_address_id(db_session)

    ticket = await test_helpers.create_ticket(client, owner_headers, address_id)
    response = await client.patch(
        f"/api/tickets/{ticket['id']}/status",
        headers=manager_headers,
        json={"status_code": "accepted"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


async def test_server_regular_user_cannot_update_ticket_status(client, db_session, test_helpers):
    await test_helpers.create_user(db_session, email="ticket-owner3@example.com")
    await test_helpers.create_user(db_session, email="regular@example.com")
    owner_headers = await test_helpers.auth_headers(client, "ticket-owner3@example.com")
    regular_headers = await test_helpers.auth_headers(client, "regular@example.com")
    address_id = await test_helpers.first_address_id(db_session)

    ticket = await test_helpers.create_ticket(client, owner_headers, address_id)
    response = await client.patch(
        f"/api/tickets/{ticket['id']}/status",
        headers=regular_headers,
        json={"status_code": "accepted"},
    )

    assert response.status_code == 403
