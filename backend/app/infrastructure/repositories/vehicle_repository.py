from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.exceptions import VehicleAlreadyExistsError, VehicleNotFoundError
from app.domain.source import Source, SourceType
from app.domain.vehicle import BodyType, FuelType, Transmission, Vehicle, VehicleClass
from app.infrastructure.models.source import SourceTable
from app.infrastructure.models.vehicle import VehicleTable


class PostgresVehicleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: VehicleTable, sources: list[SourceTable] | None = None) -> Vehicle:
        return Vehicle(
            id=row.id,
            manufacturer=row.manufacturer,
            model_name=row.model_name,
            vehicle_class=VehicleClass(row.vehicle_class),
            year=row.year,
            body_type=BodyType(row.body_type),
            transmission=Transmission(row.transmission),
            fuel_type=FuelType(row.fuel_type),
            thumbnail_url=row.thumbnail_url,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
            sources=[self._source_to_domain(s) for s in sources] if sources is not None else None,
        )

    def _source_to_domain(self, row: SourceTable) -> Source:
        return Source(
            id=row.id,
            source_type=SourceType(row.source_type),
            url=row.url,
            description=row.description,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_table(self, vehicle: Vehicle) -> VehicleTable:
        return VehicleTable(
            id=vehicle.id,
            manufacturer=vehicle.manufacturer,
            model_name=vehicle.model_name,
            vehicle_class=vehicle.vehicle_class.value,
            year=vehicle.year,
            body_type=vehicle.body_type.value,
            transmission=vehicle.transmission.value,
            fuel_type=vehicle.fuel_type.value,
            thumbnail_url=vehicle.thumbnail_url,
            notes=vehicle.notes,
            created_at=vehicle.created_at,
            updated_at=vehicle.updated_at,
        )

    async def add(self, vehicle: Vehicle) -> Vehicle:
        row = self._to_table(vehicle)
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as e:
            raise VehicleAlreadyExistsError(str(e)) from e
        return self._to_domain(row)

    async def get(self, id: UUID) -> Vehicle | None:
        result = await self._session.execute(select(VehicleTable).where(VehicleTable.id == id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def get_with_sources(self, id: UUID) -> Vehicle | None:
        result = await self._session.execute(
            select(VehicleTable)
            .options(selectinload(VehicleTable.sources))
            .where(VehicleTable.id == id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row, sources=list(row.sources))

    async def list(self) -> list[Vehicle]:
        result = await self._session.execute(select(VehicleTable))
        return [self._to_domain(row) for row in result.scalars().all()]

    async def update(self, vehicle: Vehicle) -> Vehicle:
        result = await self._session.execute(select(VehicleTable).where(VehicleTable.id == vehicle.id))
        row = result.scalar_one_or_none()
        if row is None:
            raise VehicleNotFoundError(f"Vehicle {vehicle.id} not found")
        row.manufacturer  = vehicle.manufacturer
        row.model_name    = vehicle.model_name
        row.vehicle_class = vehicle.vehicle_class.value
        row.year          = vehicle.year
        row.body_type     = vehicle.body_type.value
        row.transmission  = vehicle.transmission.value
        row.fuel_type     = vehicle.fuel_type.value
        row.thumbnail_url = vehicle.thumbnail_url
        row.notes         = vehicle.notes
        row.updated_at    = vehicle.updated_at
        try:
            await self._session.flush()
        except IntegrityError as e:
            raise VehicleAlreadyExistsError(str(e)) from e
        return self._to_domain(row)

    async def delete(self, id: UUID) -> None:
        result = await self._session.execute(select(VehicleTable).where(VehicleTable.id == id))
        row = result.scalar_one_or_none()
        if row is None:
            raise VehicleNotFoundError(f"Vehicle {id} not found")
        await self._session.delete(row)
        await self._session.flush()
