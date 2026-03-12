import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

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
    {"id": 1, "name": "Создана"},
    {"id": 2, "name": "Принята"},
    {"id": 3, "name": "В работе"},
    {"id": 4, "name": "Выполнена"},
    {"id": 5, "name": "Закрыта"},
    {"id": 6, "name": "Отклонена"},
]


async def wait_for_db(eng: AsyncEngine, retries: int = 15, delay: float = 3.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            async with eng.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Подключение к БД установлено")
            return
        except Exception as e:
            logger.warning(f"⏳ БД недоступна (попытка {attempt}/{retries}): {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
    raise RuntimeError("❌ Не удалось подключиться к БД")


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
        logger.info("✅ Все таблицы уже существуют, создание не требуется")
        return

    async with eng.begin() as conn:
        for table_name in missing_tables:
            table = Base.metadata.tables[table_name]
            await conn.run_sync(lambda sync_conn, t=table: t.create(sync_conn, checkfirst=True))

    logger.info(f"✅ Созданы отсутствующие таблицы: {', '.join(missing_tables)}")


async def seed_roles_if_empty(eng: AsyncEngine) -> None:
    if not await table_exists(eng, "roles"):
        logger.warning("⚠️ Таблица roles не существует, пропускаю заполнение")
        return

    async with eng.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM roles"))
        count = result.scalar() or 0

        if count > 0:
            logger.info("✅ Таблица roles уже заполнена, пропускаю вставку")
            return

        await conn.execute(
            text("INSERT INTO roles (id, name) VALUES (:id, :name)"),
            INITIAL_ROLES,
        )

    logger.info("✅ Начальные роли добавлены")


async def seed_ticket_statuses_if_empty(eng: AsyncEngine) -> None:
    if not await table_exists(eng, "ticket_statuses"):
        logger.warning("⚠️ Таблица ticket_statuses не существует, пропускаю заполнение")
        return

    async with eng.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM ticket_statuses"))
        count = result.scalar() or 0

        if count > 0:
            logger.info("✅ Таблица ticket_statuses уже заполнена, пропускаю вставку")
            return

        await conn.execute(
            text("INSERT INTO ticket_statuses (id, name) VALUES (:id, :name)"),
            INITIAL_TICKET_STATUSES,
        )

    logger.info("✅ Начальные статусы заявок добавлены")


async def init_db() -> None:
    logger.info("🚀 Инициализация БД...")
    await wait_for_db(engine)
    await create_tables_if_not_exist(engine)
    await seed_roles_if_empty(engine)
    await seed_ticket_statuses_if_empty(engine)
    logger.info("🎉 БД готова")