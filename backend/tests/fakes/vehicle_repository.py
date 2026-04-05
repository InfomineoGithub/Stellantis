from __future__ import annotations

from uuid import UUID

from app.domain.exceptions import VehicleAlreadyExistsError, VehicleNotFoundError
from app.domain.source import Source
from app.domain.vehicle import Vehicle


class InMemoryVehicleRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Vehicle] = {}

    async def add(self, vehicle: Vehicle) -> Vehicle:
        for v in self._store.values():
            if (v.manufacturer, v.model_name, v.year) == (vehicle.manufacturer, vehicle.model_name, vehicle.year):
                raise VehicleAlreadyExistsError(f"Vehicle {vehicle.manufacturer} {vehicle.model_name} {vehicle.year} already exists")
        self._store[vehicle.id] = vehicle
        return vehicle

    async def get(self, id: UUID) -> Vehicle | None:
        v = self._store.get(id)
        if v is None:
            return None
        return v.model_copy(update={"sources": None})

    async def get_with_sources(self, id: UUID) -> Vehicle | None:
        v = self._store.get(id)
        if v is None:
            return None
        sources = v.sources if v.sources is not None else []
        return v.model_copy(update={"sources": sources})

    async def list(self) -> list[Vehicle]:
        return [v.model_copy(update={"sources": None}) for v in self._store.values()]

    async def update(self, vehicle: Vehicle) -> Vehicle:
        if vehicle.id not in self._store:
            raise VehicleNotFoundError(f"Vehicle {vehicle.id} not found")
        for v in self._store.values():
            if v.id != vehicle.id and (v.manufacturer, v.model_name, v.year) == (vehicle.manufacturer, vehicle.model_name, vehicle.year):
                raise VehicleAlreadyExistsError(f"Vehicle {vehicle.manufacturer} {vehicle.model_name} {vehicle.year} already exists")
        self._store[vehicle.id] = vehicle
        return vehicle

    async def delete(self, id: UUID) -> None:
        if id not in self._store:
            raise VehicleNotFoundError(f"Vehicle {id} not found")
        del self._store[id]

    def _add_source_to_vehicle(self, vehicle_id: UUID, source: Source) -> None:
        v = self._store.get(vehicle_id)
        if v is None:
            return
        current = v.sources or []
        if not any(s.id == source.id for s in current):
            self._store[vehicle_id] = v.model_copy(update={"sources": current + [source]})

    def _remove_source_from_vehicle(self, vehicle_id: UUID, source_id: UUID) -> None:
        v = self._store.get(vehicle_id)
        if v is None:
            return
        current = v.sources or []
        self._store[vehicle_id] = v.model_copy(update={"sources": [s for s in current if s.id != source_id]})
