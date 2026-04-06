from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.exceptions import VehicleAlreadyExistsError, VehicleNotFoundError
from app.domain.vehicle import BodyType, CreateVehicleInput, FuelType, Transmission, UpdateVehicleInput, Vehicle, VehicleClass
from app.services.vehicle_service import VehicleService
from tests.fakes.vehicle_repository import InMemoryVehicleRepository


def make_vehicle(**kwargs) -> Vehicle:
    defaults = dict(
        id=uuid4(),
        manufacturer="Toyota",
        model_name="Camry",
        vehicle_class=VehicleClass.midsize,
        year=2024,
        body_type=BodyType.sedan,
        transmission=Transmission.automatic,
        fuel_type=FuelType.gasoline,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return Vehicle(**{**defaults, **kwargs})


@pytest.fixture
def service():
    return VehicleService(InMemoryVehicleRepository())


@pytest.mark.asyncio
async def test_create_vehicle_happy_path(service):
    input = CreateVehicleInput(
        manufacturer="Toyota",
        model_name="Camry",
        vehicle_class=VehicleClass.midsize,
        year=2024,
        body_type=BodyType.sedan,
        transmission=Transmission.automatic,
        fuel_type=FuelType.gasoline,
    )
    vehicle = await service.create(input)
    assert vehicle.manufacturer == "Toyota"
    assert vehicle.model_name == "Camry"
    assert vehicle.sources is None


@pytest.mark.asyncio
async def test_create_vehicle_duplicate_raises(service):
    input = CreateVehicleInput(
        manufacturer="Toyota",
        model_name="Camry",
        vehicle_class=VehicleClass.midsize,
        year=2024,
        body_type=BodyType.sedan,
        transmission=Transmission.automatic,
        fuel_type=FuelType.gasoline,
    )
    await service.create(input)
    with pytest.raises(VehicleAlreadyExistsError):
        await service.create(input)


@pytest.mark.asyncio
async def test_get_vehicle_not_found_raises(service):
    with pytest.raises(VehicleNotFoundError):
        await service.get(uuid4())


@pytest.mark.asyncio
async def test_update_vehicle_happy_path(service):
    input = CreateVehicleInput(
        manufacturer="Toyota",
        model_name="Camry",
        vehicle_class=VehicleClass.midsize,
        year=2024,
        body_type=BodyType.sedan,
        transmission=Transmission.automatic,
        fuel_type=FuelType.gasoline,
    )
    vehicle = await service.create(input)
    updated = await service.update(vehicle.id, UpdateVehicleInput(model_name="Corolla"))
    assert updated.model_name == "Corolla"


@pytest.mark.asyncio
async def test_delete_vehicle_happy_path(service):
    input = CreateVehicleInput(
        manufacturer="Toyota",
        model_name="Camry",
        vehicle_class=VehicleClass.midsize,
        year=2024,
        body_type=BodyType.sedan,
        transmission=Transmission.automatic,
        fuel_type=FuelType.gasoline,
    )
    vehicle = await service.create(input)
    await service.delete(vehicle.id)
    with pytest.raises(VehicleNotFoundError):
        await service.get(vehicle.id)
