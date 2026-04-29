import asyncio
import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.schema import DefaultClause

from app.core.database import engine
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
from app.models import Base

logger = logging.getLogger(__name__)

INITIAL_ROLES = [
    {"id": 1, "name": "Пользователь"},
    {"id": 2, "name": "Менеджер"},
    {"id": 3, "name": "Администратор"},
    {"id": 4, "name": "Суперпользователь"},
]

INITIAL_TICKET_STATUSES = [
    {"id": 1, "code": "created", "name": "Создана"},
    {"id": 2, "code": "accepted", "name": "Принята"},
    {"id": 3, "code": "in_progress", "name": "В работе"},
    {"id": 4, "code": "completed", "name": "Выполнена"},
    {"id": 5, "code": "closed", "name": "Закрыта"},
    {"id": 6, "code": "rejected", "name": "Отклонена"},
]

INITIAL_PERMISSIONS = [
    {"code": ADMIN_ACCESS, "name": "Доступ в админ-панель", "description": "Вход в административный интерфейс"},
    {"code": USERS_READ, "name": "Просмотр пользователей", "description": "Просмотр списка и карточек пользователей"},
    {"code": USERS_CREATE, "name": "Создание пользователей", "description": "Создание новых пользователей"},
    {"code": USERS_UPDATE, "name": "Редактирование пользователей", "description": "Изменение данных пользователей"},
    {"code": USERS_DELETE, "name": "Удаление пользователей", "description": "Удаление пользователей"},
    {"code": ROLES_READ, "name": "Просмотр ролей", "description": "Просмотр ролей и их набора прав"},
    {"code": ROLES_MANAGE, "name": "Управление ролями", "description": "Изменение ролей и назначенных им прав"},
    {"code": TICKETS_READ_ALL, "name": "Просмотр всех заявок", "description": "Просмотр всех заявок независимо от автора"},
    {"code": TICKETS_UPDATE_STATUS, "name": "Изменение статусов заявок", "description": "Обновление статусов заявок"},
    {"code": TICKETS_DELETE, "name": "Удаление заявок", "description": "Удаление заявок"},
    {"code": ADDRESS_MANAGE, "name": "Управление адресами", "description": "Изменение управ, районов, улиц и адресов"},
    {"code": REPORTS_READ, "name": "Просмотр отчетов", "description": "Доступ к отчетам по заявкам"},
    {"code": CHAT_PARTICIPANTS_MANAGE, "name": "Управление участниками чата", "description": "Добавление участников в чаты заявок"},
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

async def wait_for_db(eng: AsyncEngine, retries: int = 15, delay: float = 3.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            async with eng.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Подключение к БД установлено")
            return
        except Exception as e:
            logger.warning("БД недоступна (попытка %s/%s): %s", attempt, retries, e)
            if attempt < retries:
                await asyncio.sleep(delay)
    raise RuntimeError("Не удалось подключиться к БД")


async def table_exists(eng: AsyncEngine, table_name: str, schema: str = "public") -> bool:
    query = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table_name
        )
        """
    )
    async with eng.connect() as conn:
        result = await conn.execute(query, {"schema": schema, "table_name": table_name})
        return bool(result.scalar())


async def create_tables_if_not_exist(eng: AsyncEngine) -> None:
    model_tables = list(Base.metadata.tables.keys())

    async with eng.connect() as conn:
        existing_tables = set()

        for table_name in model_tables:
            result = await conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = :table_name
                    )
                    """
                ),
                {"table_name": table_name},
            )
            if result.scalar():
                existing_tables.add(table_name)

    missing_tables = [table for table in model_tables if table not in existing_tables]

    if not missing_tables:
        logger.info("Все таблицы уже существуют, создание не требуется")
        return

    async with eng.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[Base.metadata.tables[name] for name in missing_tables],
                checkfirst=True,
            )
        )

    logger.info("Созданы отсутствующие таблицы: %s", ", ".join(missing_tables))


def _compile_server_default(default: DefaultClause, dialect) -> str:
    if hasattr(default.arg, "compile"):
        return str(default.arg.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    return str(default.arg)


def _build_add_column_sql(table_name: str, column, dialect) -> tuple[str, bool]:
    quoted_table_name = dialect.identifier_preparer.quote(table_name)
    quoted_column_name = dialect.identifier_preparer.quote(column.name)
    column_type = column.type.compile(dialect=dialect)

    parts = [f"ALTER TABLE {quoted_table_name} ADD COLUMN {quoted_column_name} {column_type}"]

    if column.server_default is not None:
        default_sql = _compile_server_default(column.server_default, dialect)
        parts.append(f"DEFAULT {default_sql}")

    for foreign_key in column.foreign_keys:
        target_table, target_column = foreign_key.target_fullname.split(".", 1)
        quoted_target_table = dialect.identifier_preparer.quote(target_table)
        quoted_target_column = dialect.identifier_preparer.quote(target_column)
        parts.append(f"REFERENCES {quoted_target_table}({quoted_target_column})")
        break

    added_as_nullable = False
    if not column.nullable and column.server_default is None and not column.primary_key:
        added_as_nullable = True
    elif not column.nullable:
        parts.append("NOT NULL")

    return " ".join(parts), added_as_nullable


async def sync_columns_if_not_exist(eng: AsyncEngine) -> None:
    async with eng.begin() as conn:
        def _sync(sync_conn) -> list[str]:
            inspector = inspect(sync_conn)
            added_columns: list[str] = []

            for table_name, table in Base.metadata.tables.items():
                if not inspector.has_table(table_name, schema="public"):
                    continue

                existing_columns = {
                    column["name"]
                    for column in inspector.get_columns(table_name, schema="public")
                }

                for column in table.columns:
                    if column.name in existing_columns:
                        continue

                    sql, added_as_nullable = _build_add_column_sql(table_name, column, sync_conn.dialect)
                    sync_conn.execute(text(sql))
                    added_columns.append(f"{table_name}.{column.name}")

                    if added_as_nullable:
                        logger.warning(
                            "Колонка %s.%s добавлена как nullable, так как в таблице уже могут быть данные. "
                            "После заполнения данных можно сделать её NOT NULL.",
                            table_name,
                            column.name,
                        )

            return added_columns

        added_columns = await conn.run_sync(_sync)

    if added_columns:
        logger.info("Добавлены новые колонки: %s", ", ".join(added_columns))
    else:
        logger.info("Новых колонок для синхронизации не найдено")


async def seed_roles_if_empty(eng: AsyncEngine) -> None:
    if not await table_exists(eng, "roles"):
        logger.warning("Таблица roles не существует, пропускаю заполнение")
        return

    async with eng.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM roles"))
        count = result.scalar() or 0

        if count > 0:
            logger.info("Таблица roles уже заполнена, пропускаю вставку")
            return

        await conn.execute(text("INSERT INTO roles (id, name) VALUES (:id, :name)"), INITIAL_ROLES)

    logger.info("Начальные роли добавлены")


async def seed_ticket_statuses_if_empty(eng: AsyncEngine) -> None:
    if not await table_exists(eng, "ticket_statuses"):
        logger.warning("Таблица ticket_statuses не существует, пропускаю заполнение")
        return

    async with eng.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM ticket_statuses"))
        count = result.scalar() or 0

        if count > 0:
            logger.info("Таблица ticket_statuses уже заполнена, пропускаю вставку")
            return

        await conn.execute(
            text("INSERT INTO ticket_statuses (id, code, name) VALUES (:id, :code, :name)"),
            INITIAL_TICKET_STATUSES,
        )

    logger.info("Начальные статусы заявок добавлены")


async def sync_ticket_status_codes(eng: AsyncEngine) -> None:
    if not await table_exists(eng, "ticket_statuses"):
        return

    async with eng.begin() as conn:
        updated_codes = []

        for status_item in INITIAL_TICKET_STATUSES:
            result = await conn.execute(
                text(
                    """
                    UPDATE ticket_statuses
                    SET code = :code
                    WHERE id = :id
                      AND (code IS NULL OR code = '')
                    """
                ),
                {"id": status_item["id"], "code": status_item["code"]},
            )
            if result.rowcount and result.rowcount > 0:
                updated_codes.append(status_item["code"])

    if updated_codes:
        logger.info("Обновлены code у статусов заявок: %s", ", ".join(updated_codes))
    else:
        logger.info("Коды статусов заявок уже заполнены")


async def seed_permissions(eng: AsyncEngine) -> None:
    if not await table_exists(eng, "permissions"):
        logger.warning("Таблица permissions не существует, пропускаю заполнение")
        return

    async with eng.begin() as conn:
        await conn.execute(
            text(
                """
                SELECT setval(
                    pg_get_serial_sequence('permissions', 'id'),
                    COALESCE((SELECT MAX(id) FROM permissions), 1),
                    (SELECT COUNT(*) > 0 FROM permissions)
                )
                """
            )
        )

        for permission in INITIAL_PERMISSIONS:
            result = await conn.execute(
                text("SELECT id FROM permissions WHERE code = :code"),
                {"code": permission["code"]},
            )
            existing_id = result.scalar_one_or_none()

            if existing_id is None:
                await conn.execute(
                    text(
                        """
                        INSERT INTO permissions (code, name, description)
                        VALUES (:code, :name, :description)
                        """
                    ),
                    permission,
                )
            else:
                await conn.execute(
                    text(
                        """
                        UPDATE permissions
                        SET name = :name,
                            description = :description
                        WHERE code = :code
                        """
                    ),
                    permission,
                )

    logger.info("Базовые permissions синхронизированы")


async def seed_role_permissions(eng: AsyncEngine) -> None:
    if not await table_exists(eng, "role_permissions") or not await table_exists(eng, "permissions"):
        logger.warning("Таблицы role_permissions/permissions не существуют, пропускаю заполнение")
        return

    async with eng.begin() as conn:
        permissions_result = await conn.execute(text("SELECT id, code FROM permissions"))
        permission_map = {row.code: row.id for row in permissions_result}

        for role_id, permission_codes in INITIAL_ROLE_PERMISSIONS.items():
            for permission_code in permission_codes:
                permission_id = permission_map.get(permission_code)
                if permission_id is None:
                    continue
                result = await conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM role_permissions
                        WHERE role_id = :role_id
                          AND permission_id = :permission_id
                        """
                    ),
                    {"role_id": role_id, "permission_id": permission_id},
                )
                if result.scalar_one_or_none() is None:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO role_permissions (role_id, permission_id)
                            VALUES (:role_id, :permission_id)
                            """
                        ),
                        {"role_id": role_id, "permission_id": permission_id},
                    )

    logger.info("Базовые назначения permissions ролям синхронизированы")


async def init_db() -> None:
    logger.info("Инициализация БД...")
    await wait_for_db(engine)
    await create_tables_if_not_exist(engine)
    await sync_columns_if_not_exist(engine)
    await seed_roles_if_empty(engine)
    await seed_ticket_statuses_if_empty(engine)
    await sync_ticket_status_codes(engine)
    await seed_permissions(engine)
    await seed_role_permissions(engine)
    logger.info("БД готова")
