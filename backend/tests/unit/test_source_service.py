from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.exceptions import VehicleSourceLinkError
from app.domain.source import CreateSourceInput, SourceType
from app.services.source_service import SourceService
from tests.fakes.source_repository import InMemorySourceRepository


@pytest.fixture
def service():
    return SourceService(InMemorySourceRepository())


@pytest.mark.asyncio
async def test_create_source_happy_path(service):
    input = CreateSourceInput(source_type=SourceType.web_url, url="https://example.com")
    source = await service.create(input)
    assert source.url == "https://example.com"
    assert source.is_active is True


@pytest.mark.asyncio
async def test_link_vehicle_happy_path():
    from app.domain.vehicle import BodyType, FuelType, Transmission, Vehicle, VehicleClass
    from tests.fakes.vehicle_repository import InMemoryVehicleRepository

    vehicle_repo = InMemoryVehicleRepository()
    source_repo = InMemorySourceRepository()
    vehicle = Vehicle(
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
    await vehicle_repo.add(vehicle)
    service = SourceService(source_repo, vehicle_repo)
    source = await service.create(CreateSourceInput(source_type=SourceType.web_url, url="https://example.com"))
    await service.link_vehicle(source.id, vehicle.id)  # should not raise


@pytest.mark.asyncio
async def test_link_vehicle_already_linked_raises():
    source_repo = InMemorySourceRepository()
    service = SourceService(source_repo)
    source = await service.create(CreateSourceInput(source_type=SourceType.web_url, url="https://example.com"))
    vid = uuid4()
    await source_repo.link_vehicle(source.id, vid)
    with pytest.raises(VehicleSourceLinkError):
        await source_repo.link_vehicle(source.id, vid)


@pytest.mark.asyncio
async def test_unlink_vehicle_not_linked_raises():
    source_repo = InMemorySourceRepository()
    service = SourceService(source_repo)
    source = await service.create(CreateSourceInput(source_type=SourceType.web_url, url="https://example.com"))
    with pytest.raises(VehicleSourceLinkError):
        await source_repo.unlink_vehicle(source.id, uuid4())
