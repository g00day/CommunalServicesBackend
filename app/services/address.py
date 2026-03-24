from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ADDRESS_MANAGE, has_permission
from app.models import Address, District, Street, Uprava, User
from app.schemas import AddressOut, DistrictOut, StreetOut, UpravaOut


def _ensure_address_manager(user: User) -> None:
    if not has_permission(user, ADDRESS_MANAGE):
        raise HTTPException(status_code=403, detail="Управление адресами требует отдельного права")


async def _get_uprava(db: AsyncSession, uprava_id: int) -> Uprava:
    result = await db.execute(select(Uprava).where(Uprava.id == uprava_id))
    uprava = result.scalar_one_or_none()
    if not uprava:
        raise HTTPException(status_code=404, detail="Управа не найдена")
    return uprava


async def _get_district(db: AsyncSession, district_id: int) -> District:
    result = await db.execute(select(District).where(District.id == district_id))
    district = result.scalar_one_or_none()
    if not district:
        raise HTTPException(status_code=404, detail="Район не найден")
    return district


async def _get_street(db: AsyncSession, street_id: int) -> Street:
    result = await db.execute(select(Street).where(Street.id == street_id))
    street = result.scalar_one_or_none()
    if not street:
        raise HTTPException(status_code=404, detail="Улица не найдена")
    return street


async def get_upravas_service(db: AsyncSession) -> list[UpravaOut]:
    result = await db.execute(select(Uprava).order_by(Uprava.name))
    return [UpravaOut(id=item.id, name=item.name) for item in result.scalars().all()]


async def create_uprava_service(db: AsyncSession, name: str, current_user: User) -> UpravaOut:
    _ensure_address_manager(current_user)
    uprava = Uprava(name=name)
    db.add(uprava)
    await db.commit()
    await db.refresh(uprava)
    return UpravaOut(id=uprava.id, name=uprava.name)


async def get_districts_service(db: AsyncSession, uprava_id: int | None = None) -> list[DistrictOut]:
    query = select(District).order_by(District.name)
    if uprava_id is not None:
        query = query.where(District.uprava_id == uprava_id)
    result = await db.execute(query)
    return [DistrictOut(id=item.id, uprava_id=item.uprava_id, name=item.name) for item in result.scalars().all()]


async def create_district_service(db: AsyncSession, uprava_id: int, name: str, current_user: User) -> DistrictOut:
    _ensure_address_manager(current_user)
    await _get_uprava(db, uprava_id)
    district = District(uprava_id=uprava_id, name=name)
    db.add(district)
    await db.commit()
    await db.refresh(district)
    return DistrictOut(id=district.id, uprava_id=district.uprava_id, name=district.name)


async def get_streets_service(db: AsyncSession, district_id: int | None = None) -> list[StreetOut]:
    query = select(Street).order_by(Street.name)
    if district_id is not None:
        query = query.where(Street.district_id == district_id)
    result = await db.execute(query)
    return [StreetOut(id=item.id, district_id=item.district_id, name=item.name) for item in result.scalars().all()]


async def create_street_service(db: AsyncSession, district_id: int, name: str, current_user: User) -> StreetOut:
    _ensure_address_manager(current_user)
    await _get_district(db, district_id)
    street = Street(district_id=district_id, name=name)
    db.add(street)
    await db.commit()
    await db.refresh(street)
    return StreetOut(id=street.id, district_id=street.district_id, name=street.name)


async def get_addresses_service(db: AsyncSession, street_id: int | None = None) -> list[AddressOut]:
    query = select(Address).order_by(Address.house_number)
    if street_id is not None:
        query = query.where(Address.street_id == street_id)
    result = await db.execute(query)
    return [AddressOut(id=item.id, street_id=item.street_id, house_number=item.house_number) for item in result.scalars().all()]


async def create_address_service(
    db: AsyncSession,
    street_id: int,
    house_number: str,
    current_user: User,
) -> AddressOut:
    _ensure_address_manager(current_user)
    await _get_street(db, street_id)
    address = Address(street_id=street_id, house_number=house_number)
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return AddressOut(id=address.id, street_id=address.street_id, house_number=address.house_number)
