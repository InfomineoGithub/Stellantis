from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.exceptions import SourceNotFoundError
from app.domain.repositories import ISourceRepository, IVehicleRepository
from app.domain.source import CreateSourceInput, Source, UpdateSourceInput
from app.domain.vehicle import Vehicle


class SourceService:
    def __init__(self, repo: ISourceRepository, vehicle_repo: IVehicleRepository | None = None) -> None:
        self._repo = repo
        self._vehicle_repo = vehicle_repo

    async def create(self, input: CreateSourceInput) -> Source:
        now = datetime.now(UTC)
        source = Source(
            id=uuid4(),
            source_type=input.source_type,
            url=input.url,
            description=input.description,
            is_active=input.is_active,
            created_at=now,
            updated_at=now,
        )
        return await self._repo.add(source)

    async def get(self, id: UUID) -> Source:
        source = await self._repo.get(id)
        if source is None:
            raise SourceNotFoundError(f"Source {id} not found")
        return source

    async def list(self) -> list[Source]:
        return await self._repo.list()

    async def update(self, id: UUID, input: UpdateSourceInput) -> Source:
        source = await self.get(id)
        updated = source.model_copy(update={
            k: v for k, v in input.model_dump(exclude_unset=True).items() if v is not None
        })
        updated = updated.model_copy(update={"updated_at": datetime.now(UTC)})
        return await self._repo.update(updated)

    async def delete(self, id: UUID) -> None:
        await self.get(id)
        await self._repo.delete(id)

    async def link_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None:
        await self.get(source_id)
        if self._vehicle_repo:
            vehicle = await self._vehicle_repo.get(vehicle_id)
            from app.domain.exceptions import VehicleNotFoundError
            if vehicle is None:
                raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")
        await self._repo.link_vehicle(source_id, vehicle_id)

    async def unlink_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None:
        await self.get(source_id)
        await self._repo.unlink_vehicle(source_id, vehicle_id)

    async def get_vehicles_for_source(self, source_id: UUID) -> list[Vehicle]:
        await self.get(source_id)
        return await self._repo.get_vehicles_for_source(source_id)
