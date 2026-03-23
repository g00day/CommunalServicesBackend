import asyncio
import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.schema import DefaultClause

from app.core.database import engine
from app.models import Base  # регистрирует все модели

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


async def wait_for_db(eng: AsyncEngine, retries: int = 15, delay: float = 3.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            async with eng.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Подключение к БД установлено")
            return
        except Exception as e:
            logger.warning(f"БД недоступна (попытка {attempt}/{retries}): {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
    raise RuntimeError("Не удалось подключиться к БД")


async def table_exists(eng: AsyncEngine, table_name: str, schema: str = "public") -> bool:
    query = text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table_name
        )
    """)
    async with eng.connect() as conn:
        result = await conn.execute(query, {"schema": schema, "table_name": table_name})
        return bool(result.scalar())


async def create_tables_if_not_exist(eng: AsyncEngine) -> None:
    model_tables = list(Base.metadata.tables.keys())

    async with eng.connect() as conn:
        existing_tables = set()

        for table_name in model_tables:
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = :table_name
                    )
                """),
                {"table_name": table_name},
            )
            if result.scalar():
                existing_tables.add(table_name)

    missing_tables = [table for table in model_tables if table not in existing_tables]

    if not missing_tables:
        logger.info("Все таблицы уже существуют, создание не требуется")
        return

    async with eng.begin() as conn:
        for table_name in missing_tables:
            table = Base.metadata.tables[table_name]
            await conn.run_sync(lambda sync_conn, t=table: t.create(sync_conn, checkfirst=True))

    logger.info(f"Созданы отсутствующие таблицы: {', '.join(missing_tables)}")


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
                text("""
                    UPDATE ticket_statuses
                    SET code = :code
                    WHERE id = :id
                      AND (code IS NULL OR code = '')
                """),
                {"id": status_item["id"], "code": status_item["code"]},
            )
            if result.rowcount and result.rowcount > 0:
                updated_codes.append(status_item["code"])

    if updated_codes:
        logger.info("Обновлены code у статусов заявок: %s", ", ".join(updated_codes))
    else:
        logger.info("Коды статусов заявок уже заполнены")


async def init_db() -> None:
    logger.info("Инициализация БД...")
    await wait_for_db(engine)
    await create_tables_if_not_exist(engine)
    await sync_columns_if_not_exist(engine)
    await seed_roles_if_empty(engine)
    await seed_ticket_statuses_if_empty(engine)
    await sync_ticket_status_codes(engine)
    logger.info("БД готова")
