from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import (
    SourceAlreadyExistsError,
    SourceNotFoundError,
    VehicleNotFoundError,
    VehicleSourceLinkError,
)
from app.domain.source import Source, SourceType
from app.domain.vehicle import BodyType, FuelType, Transmission, Vehicle, VehicleClass
from app.infrastructure.models.associations import vehicle_sources
from app.infrastructure.models.source import SourceTable
from app.infrastructure.models.vehicle import VehicleTable


class PostgresSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: SourceTable) -> Source:
        return Source(
            id=row.id,
            source_type=SourceType(row.source_type),
            url=row.url,
            description=row.description,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _vehicle_to_domain(self, row: VehicleTable) -> Vehicle:
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
        )

    def _to_table(self, source: Source) -> SourceTable:
        return SourceTable(
            id=source.id,
            source_type=source.source_type.value,
            url=source.url,
            description=source.description,
            is_active=source.is_active,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    async def add(self, source: Source) -> Source:
        row = self._to_table(source)
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as e:
            raise SourceAlreadyExistsError(str(e)) from e
        return self._to_domain(row)

    async def get(self, id: UUID) -> Source | None:
        result = await self._session.execute(select(SourceTable).where(SourceTable.id == id))
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def list(self) -> list[Source]:
        result = await self._session.execute(select(SourceTable))
        return [self._to_domain(row) for row in result.scalars().all()]

    async def update(self, source: Source) -> Source:
        result = await self._session.execute(select(SourceTable).where(SourceTable.id == source.id))
        row = result.scalar_one_or_none()
        if row is None:
            raise SourceNotFoundError(f"Source {source.id} not found")
        row.source_type = source.source_type.value
        row.url = source.url
        row.description = source.description
        row.is_active = source.is_active
        row.updated_at = source.updated_at
        try:
            await self._session.flush()
        except IntegrityError as e:
            raise SourceAlreadyExistsError(str(e)) from e
        return self._to_domain(row)

    async def delete(self, id: UUID) -> None:
        result = await self._session.execute(select(SourceTable).where(SourceTable.id == id))
        row = result.scalar_one_or_none()
        if row is None:
            raise SourceNotFoundError(f"Source {id} not found")
        await self._session.delete(row)
        await self._session.flush()

    async def link_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None:
        # Check source exists
        s_result = await self._session.execute(select(SourceTable).where(SourceTable.id == source_id))
        if s_result.scalar_one_or_none() is None:
            raise SourceNotFoundError(f"Source {source_id} not found")
        # Check vehicle exists
        v_result = await self._session.execute(select(VehicleTable).where(VehicleTable.id == vehicle_id))
        if v_result.scalar_one_or_none() is None:
            raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")
        # Check not already linked
        existing = await self._session.execute(
            select(vehicle_sources).where(
                vehicle_sources.c.source_id == source_id,
                vehicle_sources.c.vehicle_id == vehicle_id,
            )
        )
        if existing.first() is not None:
            raise VehicleSourceLinkError(f"Vehicle {vehicle_id} already linked to source {source_id}")
        await self._session.execute(vehicle_sources.insert().values(vehicle_id=vehicle_id, source_id=source_id))
        await self._session.flush()

    async def unlink_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None:
        existing = await self._session.execute(
            select(vehicle_sources).where(
                vehicle_sources.c.source_id == source_id,
                vehicle_sources.c.vehicle_id == vehicle_id,
            )
        )
        if existing.first() is None:
            raise VehicleSourceLinkError(f"Vehicle {vehicle_id} not linked to source {source_id}")
        await self._session.execute(
            vehicle_sources.delete().where(
                vehicle_sources.c.source_id == source_id,
                vehicle_sources.c.vehicle_id == vehicle_id,
            )
        )
        await self._session.flush()

    async def get_vehicles_for_source(self, source_id: UUID) -> list[Vehicle]:
        if (await self._session.execute(select(SourceTable).where(SourceTable.id == source_id))).scalar_one_or_none() is None:
            raise SourceNotFoundError(f"Source {source_id} not found")
        result = await self._session.execute(select(VehicleTable).join(vehicle_sources, VehicleTable.id == vehicle_sources.c.vehicle_id).where(vehicle_sources.c.source_id == source_id))
        return [self._vehicle_to_domain(row) for row in result.scalars().all()]
