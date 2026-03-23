from pydantic import BaseModel, Field


class UpravaCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)


class UpravaOut(BaseModel):
    id: int
    name: str


class DistrictCreate(BaseModel):
    uprava_id: int
    name: str = Field(min_length=2, max_length=150)


class DistrictOut(BaseModel):
    id: int
    uprava_id: int
    name: str


class StreetCreate(BaseModel):
    district_id: int
    name: str = Field(min_length=2, max_length=150)


class StreetOut(BaseModel):
    id: int
    district_id: int
    name: str


class AddressCreate(BaseModel):
    street_id: int
    house_number: str = Field(min_length=1, max_length=20)


class AddressOut(BaseModel):
    id: int
    street_id: int
    house_number: str
