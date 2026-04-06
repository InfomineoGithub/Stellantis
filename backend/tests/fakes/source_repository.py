from __future__ import annotations

from uuid import UUID

from app.domain.exceptions import (
    SourceAlreadyExistsError,
    SourceNotFoundError,
    VehicleSourceLinkError,
)
from app.domain.source import Source
from app.domain.vehicle import Vehicle


class InMemorySourceRepository:
    def __init__(self, vehicle_store: dict | None = None) -> None:
        self._store: dict[UUID, Source] = {}
        self._links: dict[UUID, set[UUID]] = {}  # source_id -> set of vehicle_ids
        self._vehicle_store: dict[UUID, Vehicle] = vehicle_store or {}

    async def add(self, source: Source) -> Source:
        for s in self._store.values():
            if s.url == source.url:
                raise SourceAlreadyExistsError(f"Source with URL {source.url} already exists")
        self._store[source.id] = source
        self._links[source.id] = set()
        return source

    async def get(self, id: UUID) -> Source | None:
        return self._store.get(id)

    async def list(self) -> list[Source]:
        return list(self._store.values())

    async def update(self, source: Source) -> Source:
        if source.id not in self._store:
            raise SourceNotFoundError(f"Source {source.id} not found")
        for s in self._store.values():
            if s.id != source.id and s.url == source.url:
                raise SourceAlreadyExistsError(f"Source with URL {source.url} already exists")
        self._store[source.id] = source
        return source

    async def delete(self, id: UUID) -> None:
        if id not in self._store:
            raise SourceNotFoundError(f"Source {id} not found")
        del self._store[id]
        self._links.pop(id, None)

    async def link_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None:
        if source_id not in self._store:
            raise SourceNotFoundError(f"Source {source_id} not found")
        links = self._links.setdefault(source_id, set())
        if vehicle_id in links:
            raise VehicleSourceLinkError(f"Vehicle {vehicle_id} already linked to source {source_id}")
        links.add(vehicle_id)

    async def unlink_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None:
        if source_id not in self._store:
            raise SourceNotFoundError(f"Source {source_id} not found")
        links = self._links.get(source_id, set())
        if vehicle_id not in links:
            raise VehicleSourceLinkError(f"Vehicle {vehicle_id} not linked to source {source_id}")
        links.remove(vehicle_id)

    async def get_vehicles_for_source(self, source_id: UUID) -> list[Vehicle]:
        if source_id not in self._store:
            raise SourceNotFoundError(f"Source {source_id} not found")
        vehicle_ids = self._links.get(source_id, set())
        return [v for vid in vehicle_ids if (v := self._vehicle_store.get(vid)) is not None]
