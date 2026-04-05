from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.exceptions import VehicleNotFoundError
from app.domain.repositories import IVehicleRepository
from app.domain.vehicle import CreateVehicleInput, UpdateVehicleInput, Vehicle


class VehicleService:
    def __init__(self, repo: IVehicleRepository) -> None:
        self._repo = repo

    async def create(self, input: CreateVehicleInput) -> Vehicle:
        now = datetime.now(UTC)
        vehicle = Vehicle(
            id=uuid4(),
            manufacturer=input.manufacturer,
            model_name=input.model_name,
            vehicle_class=input.vehicle_class,
            year=input.year,
            body_type=input.body_type,
            transmission=input.transmission,
            fuel_type=input.fuel_type,
            thumbnail_url=input.thumbnail_url,
            notes=input.notes,
            created_at=now,
            updated_at=now,
        )
        return await self._repo.add(vehicle)

    async def get(self, id: UUID) -> Vehicle:
        vehicle = await self._repo.get(id)
        if vehicle is None:
            raise VehicleNotFoundError(f"Vehicle {id} not found")
        return vehicle

    async def get_with_sources(self, id: UUID) -> Vehicle:
        vehicle = await self._repo.get_with_sources(id)
        if vehicle is None:
            raise VehicleNotFoundError(f"Vehicle {id} not found")
        return vehicle

    async def list(self) -> list[Vehicle]:
        return await self._repo.list()

    async def update(self, id: UUID, input: UpdateVehicleInput) -> Vehicle:
        vehicle = await self.get(id)
        updated = vehicle.model_copy(update={
            k: v for k, v in input.model_dump(exclude_unset=True).items() if v is not None
        })
        updated = updated.model_copy(update={"updated_at": datetime.now(UTC)})
        return await self._repo.update(updated)

    async def delete(self, id: UUID) -> None:
        await self.get(id)
        await self._repo.delete(id)
