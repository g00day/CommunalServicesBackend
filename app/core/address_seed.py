import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

INITIAL_ADDRESS_TREE = [
    {
        "uprava": "Центральная управа",
        "districts": [
            {
                "name": "Тверской район",
                "streets": [
                    {"name": "Тверская улица", "houses": ["1", "3", "7", "12"]},
                    {"name": "Большая Никитская улица", "houses": ["5", "9", "14"]},
                ],
            },
            {
                "name": "Пресненский район",
                "streets": [
                    {"name": "Красная Пресня", "houses": ["8", "16", "24"]},
                    {"name": "Звенигородское шоссе", "houses": ["11", "15"]},
                ],
            },
        ],
    },
    {
        "uprava": "Северная управа",
        "districts": [
            {
                "name": "Сокол",
                "streets": [
                    {"name": "Ленинградский проспект", "houses": ["48", "52", "56"]},
                    {"name": "Новопесчаная улица", "houses": ["17", "21"]},
                ],
            },
            {
                "name": "Аэропорт",
                "streets": [
                    {"name": "Улица Черняховского", "houses": ["4", "10"]},
                    {"name": "Планетная улица", "houses": ["29"]},
                ],
            },
        ],
    },
]


async def seed_addresses_if_empty(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('uprava', 'district', 'street', 'address')
                """
            )
        )
        table_count = result.scalar() or 0
        if table_count < 4:
            logger.warning("Address seed skipped because address tables are not fully created yet")
            return

        result = await conn.execute(text("SELECT COUNT(*) FROM address"))
        address_count = result.scalar() or 0
        if address_count > 0:
            logger.info("Address seed skipped because address table already has data")
            return

        async def get_or_create_uprava(name: str) -> int:
            result = await conn.execute(
                text("SELECT id FROM uprava WHERE name = :name LIMIT 1"),
                {"name": name},
            )
            existing_id = result.scalar_one_or_none()
            if existing_id is not None:
                return existing_id

            result = await conn.execute(
                text("INSERT INTO uprava (name) VALUES (:name) RETURNING id"),
                {"name": name},
            )
            return result.scalar_one()

        async def get_or_create_district(uprava_id: int, name: str) -> int:
            result = await conn.execute(
                text(
                    """
                    SELECT id
                    FROM district
                    WHERE uprava_id = :uprava_id AND name = :name
                    LIMIT 1
                    """
                ),
                {"uprava_id": uprava_id, "name": name},
            )
            existing_id = result.scalar_one_or_none()
            if existing_id is not None:
                return existing_id

            result = await conn.execute(
                text(
                    """
                    INSERT INTO district (uprava_id, name)
                    VALUES (:uprava_id, :name)
                    RETURNING id
                    """
                ),
                {"uprava_id": uprava_id, "name": name},
            )
            return result.scalar_one()

        async def get_or_create_street(district_id: int, name: str) -> int:
            result = await conn.execute(
                text(
                    """
                    SELECT id
                    FROM street
                    WHERE district_id = :district_id AND name = :name
                    LIMIT 1
                    """
                ),
                {"district_id": district_id, "name": name},
            )
            existing_id = result.scalar_one_or_none()
            if existing_id is not None:
                return existing_id

            result = await conn.execute(
                text(
                    """
                    INSERT INTO street (district_id, name)
                    VALUES (:district_id, :name)
                    RETURNING id
                    """
                ),
                {"district_id": district_id, "name": name},
            )
            return result.scalar_one()

        inserted_addresses = 0

        for uprava_item in INITIAL_ADDRESS_TREE:
            uprava_id = await get_or_create_uprava(uprava_item["uprava"])

            for district_item in uprava_item["districts"]:
                district_id = await get_or_create_district(uprava_id, district_item["name"])

                for street_item in district_item["streets"]:
                    street_id = await get_or_create_street(district_id, street_item["name"])

                    for house_number in street_item["houses"]:
                        await conn.execute(
                            text(
                                """
                                INSERT INTO address (street_id, house_number)
                                VALUES (:street_id, :house_number)
                                """
                            ),
                            {"street_id": street_id, "house_number": house_number},
                        )
                        inserted_addresses += 1

    logger.info("Seeded %s demo addresses", inserted_addresses)
