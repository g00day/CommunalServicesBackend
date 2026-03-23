from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    AddressCreate,
    AddressOut,
    DistrictCreate,
    DistrictOut,
    StreetCreate,
    StreetOut,
    UpravaCreate,
    UpravaOut,
)
from app.services.address import (
    create_address_service,
    create_district_service,
    create_street_service,
    create_uprava_service,
    get_addresses_service,
    get_districts_service,
    get_streets_service,
    get_upravas_service,
)


router = APIRouter(prefix="/address", tags=["address"])


@router.get("/upravas", response_model=list[UpravaOut])
async def get_upravas(db: AsyncSession = Depends(get_db)):
    return await get_upravas_service(db)


@router.post("/upravas", response_model=UpravaOut)
async def create_uprava(
    payload: UpravaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_uprava_service(db, payload.name, current_user)


@router.get("/districts", response_model=list[DistrictOut])
async def get_districts(
    uprava_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await get_districts_service(db, uprava_id)


@router.post("/districts", response_model=DistrictOut)
async def create_district(
    payload: DistrictCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_district_service(db, payload.uprava_id, payload.name, current_user)


@router.get("/streets", response_model=list[StreetOut])
async def get_streets(
    district_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await get_streets_service(db, district_id)


@router.post("/streets", response_model=StreetOut)
async def create_street(
    payload: StreetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_street_service(db, payload.district_id, payload.name, current_user)


@router.get("/addresses", response_model=list[AddressOut])
async def get_addresses(
    street_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await get_addresses_service(db, street_id)


@router.post("/addresses", response_model=AddressOut)
async def create_address(
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_address_service(db, payload.street_id, payload.house_number, current_user)
