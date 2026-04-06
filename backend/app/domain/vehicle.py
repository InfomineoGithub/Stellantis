from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class VehicleClass(StrEnum):
    compact = "compact"
    midsize = "midsize"
    full_size = "full_size"
    luxury = "luxury"
    economy = "economy"


class BodyType(StrEnum):
    sedan = "sedan"
    suv = "suv"
    hatchback = "hatchback"
    coupe = "coupe"
    convertible = "convertible"
    pickup = "pickup"
    van = "van"


class Transmission(StrEnum):
    manual = "manual"
    automatic = "automatic"
    cvt = "cvt"


class FuelType(StrEnum):
    gasoline = "gasoline"
    diesel = "diesel"
    electric = "electric"
    hybrid = "hybrid"
    phev = "phev"
    bev = "bev"


class Vehicle(BaseModel):
    id: UUID
    manufacturer: str
    model_name: str
    vehicle_class: VehicleClass
    year: int
    body_type: BodyType
    transmission: Transmission
    fuel_type: FuelType
    thumbnail_url: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    sources: list[Source] | None = None


class CreateVehicleInput(BaseModel):
    manufacturer: str
    model_name: str
    vehicle_class: VehicleClass
    year: int
    body_type: BodyType
    transmission: Transmission
    fuel_type: FuelType
    thumbnail_url: str | None = None
    notes: str | None = None


class UpdateVehicleInput(BaseModel):
    manufacturer: str | None = None
    model_name: str | None = None
    vehicle_class: VehicleClass | None = None
    year: int | None = None
    body_type: BodyType | None = None
    transmission: Transmission | None = None
    fuel_type: FuelType | None = None
    thumbnail_url: str | None = None
    notes: str | None = None


from app.domain.source import Source  # noqa: E402 — resolve forward ref

Vehicle.model_rebuild()
