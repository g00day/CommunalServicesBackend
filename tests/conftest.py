import os
import sys
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("APP_NAME", "zhkh-dispatcher-api-tests")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_DAYS", "14")
os.environ.setdefault("CHAT_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("POSTGRES_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("APP_BASE_URL", "http://testserver")
os.environ.setdefault("MAIL_USERNAME", "test@example.com")
os.environ.setdefault("MAIL_PASSWORD", "test-password")
os.environ.setdefault("MAIL_FROM", "test@example.com")
os.environ.setdefault("MAIL_SERVER", "smtp.test.local")
os.environ.setdefault("MAIL_PORT", "1025")
os.environ.setdefault("MAIL_SSL", "false")
os.environ.setdefault("MAIL_TLS", "false")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("S3_ACCESS_KEY_ID", "test-access-key")
os.environ.setdefault("S3_SECRET_ACCESS_KEY", "test-secret-key")
os.environ.setdefault("S3_PUBLIC_BASE_URL", "http://files.test.local")

from app.core.database import get_db
from app.core.permissions import (
    ADDRESS_MANAGE,
    ADMIN_ACCESS,
    CHAT_PARTICIPANTS_MANAGE,
    REPORTS_READ,
    ROLES_MANAGE,
    ROLES_READ,
    TICKETS_DELETE,
    TICKETS_READ_ALL,
    TICKETS_UPDATE_STATUS,
    USERS_CREATE,
    USERS_DELETE,
    USERS_READ,
    USERS_UPDATE,
)
from app.core.security import create_email_confirm_token, create_reset_password_token, hash_password
from app.main import app
from app.models import (
    Address,
    Base,
    District,
    Permission,
    Role,
    RolePermission,
    Street,
    TelegramLinkCode,
    TicketStatus,
    Uprava,
    User,
)

TEST_DATABASE_URL = os.environ["POSTGRES_URL"]

engine = create_async_engine(TEST_DATABASE_URL, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

INITIAL_ROLES = [
    {"id": 1, "name": "Пользователь"},
    {"id": 2, "name": "Менеджер"},
    {"id": 3, "name": "Администратор"},
    {"id": 4, "name": "Суперпользователь"},
]

INITIAL_STATUSES = [
    {"id": 1, "code": "created", "name": "Создана"},
    {"id": 2, "code": "accepted", "name": "Принята"},
    {"id": 3, "code": "in_progress", "name": "В работе"},
    {"id": 4, "code": "completed", "name": "Выполнена"},
    {"id": 5, "code": "closed", "name": "Закрыта"},
    {"id": 6, "code": "rejected", "name": "Отклонена"},
]

INITIAL_PERMISSIONS = [
    {"code": ADMIN_ACCESS, "name": "Доступ в админ-панель"},
    {"code": USERS_READ, "name": "Просмотр пользователей"},
    {"code": USERS_CREATE, "name": "Создание пользователей"},
    {"code": USERS_UPDATE, "name": "Редактирование пользователей"},
    {"code": USERS_DELETE, "name": "Удаление пользователей"},
    {"code": ROLES_READ, "name": "Просмотр ролей"},
    {"code": ROLES_MANAGE, "name": "Управление ролями"},
    {"code": TICKETS_READ_ALL, "name": "Просмотр всех заявок"},
    {"code": TICKETS_UPDATE_STATUS, "name": "Изменение статуса заявок"},
    {"code": TICKETS_DELETE, "name": "Удаление заявок"},
    {"code": ADDRESS_MANAGE, "name": "Управление адресами"},
    {"code": REPORTS_READ, "name": "Просмотр отчетов"},
    {"code": CHAT_PARTICIPANTS_MANAGE, "name": "Управление участниками чата"},
]

INITIAL_ROLE_PERMISSIONS = {
    1: [],
    2: [TICKETS_READ_ALL, TICKETS_UPDATE_STATUS, REPORTS_READ, CHAT_PARTICIPANTS_MANAGE],
    3: [
        ADMIN_ACCESS,
        USERS_READ,
        USERS_CREATE,
        USERS_UPDATE,
        USERS_DELETE,
        ROLES_READ,
        TICKETS_READ_ALL,
        TICKETS_UPDATE_STATUS,
        TICKETS_DELETE,
        ADDRESS_MANAGE,
        REPORTS_READ,
        CHAT_PARTICIPANTS_MANAGE,
    ],
    4: [
        ADMIN_ACCESS,
        USERS_READ,
        USERS_CREATE,
        USERS_UPDATE,
        USERS_DELETE,
        ROLES_READ,
        ROLES_MANAGE,
        TICKETS_READ_ALL,
        TICKETS_UPDATE_STATUS,
        TICKETS_DELETE,
        ADDRESS_MANAGE,
        REPORTS_READ,
        CHAT_PARTICIPANTS_MANAGE,
    ],
}


async def override_get_db() -> AsyncIterator:
    async with SessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def stub_external_integrations(monkeypatch: pytest.MonkeyPatch) -> dict:
    sent_emails: list[dict] = []
    uploaded_files: list[dict] = []

    async def fake_send_confirmation_email(to_email: str, token: str) -> None:
        sent_emails.append({"kind": "confirmation", "to_email": to_email, "token": token})

    async def fake_send_password_reset_email(to_email: str, token: str) -> None:
        sent_emails.append({"kind": "password_reset", "to_email": to_email, "token": token})

    async def fake_upload_file_to_storage(upload_file, scope: str, owner_id: int) -> tuple[str, str]:
        filename = upload_file.filename or "file"
        object_key = f"{scope}/{owner_id}/{filename}"
        uploaded_files.append({"scope": scope, "owner_id": owner_id, "filename": filename, "object_key": object_key})
        return object_key, f"http://files.test.local/{object_key}"

    async def fake_generate_download_url(file_url: str | None = None, file_path: str | None = None, expires_in: int = 3600) -> str:
        target = file_path or file_url or "missing-file"
        return f"http://files.test.local/{target}?expires_in={expires_in}"

    monkeypatch.setattr("app.core.mail.send_confirmation_email", fake_send_confirmation_email)
    monkeypatch.setattr("app.core.mail.send_password_reset_email", fake_send_password_reset_email)
    monkeypatch.setattr("app.services.auth.send_confirmation_email", fake_send_confirmation_email)
    monkeypatch.setattr("app.services.auth.send_password_reset_email", fake_send_password_reset_email)
    monkeypatch.setattr("app.core.storage.upload_file_to_storage", fake_upload_file_to_storage)
    monkeypatch.setattr("app.core.storage.generate_download_url", fake_generate_download_url)
    monkeypatch.setattr("app.services.ticket.upload_file_to_storage", fake_upload_file_to_storage)
    monkeypatch.setattr("app.services.ticket.generate_download_url", fake_generate_download_url)
    monkeypatch.setattr("app.services.ticket_chat.upload_file_to_storage", fake_upload_file_to_storage)
    monkeypatch.setattr("app.services.ticket_chat.generate_download_url", fake_generate_download_url)
    monkeypatch.setattr("app.routers.tickets.register_new_ticket_for_retraining", lambda: False)
    return {"sent_emails": sent_emails, "uploaded_files": uploaded_files}


@pytest.fixture(autouse=True)
async def reset_database() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    await seed_reference_data()
    yield

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def seed_reference_data() -> None:
    async with SessionLocal() as session:
        session.add_all(Role(**role_data) for role_data in INITIAL_ROLES)
        session.add_all(TicketStatus(**status_data) for status_data in INITIAL_STATUSES)
        await session.flush()

        permissions_by_code: dict[str, Permission] = {}
        for permission_data in INITIAL_PERMISSIONS:
            permission = Permission(
                code=permission_data["code"],
                name=permission_data["name"],
                description=permission_data["name"],
            )
            permissions_by_code[permission.code] = permission
            session.add(permission)

        await session.flush()

        for role_id, permission_codes in INITIAL_ROLE_PERMISSIONS.items():
            for permission_code in permission_codes:
                session.add(
                    RolePermission(
                        role_id=role_id,
                        permission_id=permissions_by_code[permission_code].id,
                    )
                )

        uprava = Uprava(name="Центральная управа")
        district = District(name="Тверской район", uprava=uprava)
        street = Street(name="Тверская улица", district=district)
        address = Address(street=street, house_number="1")
        session.add_all([uprava, district, street, address])
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session


@pytest.fixture
def test_helpers():
    class TestHelpers:
        @staticmethod
        async def create_user(
            session,
            *,
            email: str,
            password: str = "Password123!",
            role_id: int = 1,
            is_activated: bool = True,
            name: str = "Иван",
            surname: str = "Иванов",
            father_name: str | None = None,
            tg_chat_id: int | None = None,
            avatar_url: str | None = None,
            avatar_path: str | None = None,
        ) -> User:
            user = User(
                email=email,
                hash_pass=hash_password(password),
                role_id=role_id,
                is_activated=is_activated,
                name=name,
                surname=surname,
                father_name=father_name,
                tg_chat_id=tg_chat_id,
                avatar_url=avatar_url,
                avatar_path=avatar_path,
            )
            session.add(user)
            await session.commit()
            result = await session.execute(select(User).where(User.email == email))
            return result.scalar_one()

        @staticmethod
        async def auth_headers(client: AsyncClient, email: str, password: str = "Password123!") -> dict[str, str]:
            response = await client.post(
                "/api/auth/login",
                json={"email": email, "password": password},
            )
            assert response.status_code == 200, response.text
            token = response.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}

        @staticmethod
        async def create_ticket(client: AsyncClient, headers: dict[str, str], address_id: int, title: str = "Тестовая заявка", description: str | None = None):
            data = {"title": title, "address_id": str(address_id)}
            if description is not None:
                data["description"] = description
            response = await client.post("/api/tickets", headers=headers, data=data)
            assert response.status_code == 201, response.text
            return response.json()

        @staticmethod
        async def first_address_id(session) -> int:
            result = await session.execute(select(Address.id).limit(1))
            return result.scalar_one()

        @staticmethod
        async def first_street_id(session) -> int:
            result = await session.execute(select(Street.id).limit(1))
            return result.scalar_one()

        @staticmethod
        async def first_district_id(session) -> int:
            result = await session.execute(select(District.id).limit(1))
            return result.scalar_one()

        @staticmethod
        async def first_uprava_id(session) -> int:
            result = await session.execute(select(Uprava.id).limit(1))
            return result.scalar_one()

        @staticmethod
        def email_confirm_token(email: str) -> str:
            return create_email_confirm_token(email)

        @staticmethod
        def password_reset_token(email: str) -> str:
            return create_reset_password_token(email)

        @staticmethod
        async def create_telegram_link_code(session, user_id: int, code: str = "123456") -> TelegramLinkCode:
            link_code = TelegramLinkCode(
                user_id=user_id,
                code=code,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(link_code)
            await session.commit()
            return link_code

    return TestHelpers
