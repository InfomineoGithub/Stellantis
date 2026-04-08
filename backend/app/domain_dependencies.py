from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories import ISourceRepository, IVehicleRepository
from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.repositories.source_repository import PostgresSourceRepository
from app.infrastructure.repositories.vehicle_repository import PostgresVehicleRepository
from app.services.source_service import SourceService
from app.services.vehicle_service import VehicleService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session


def get_vehicle_repo(session: AsyncSession = Depends(get_db)) -> IVehicleRepository:
    return PostgresVehicleRepository(session)


def get_vehicle_service(repo: IVehicleRepository = Depends(get_vehicle_repo)) -> VehicleService:
    return VehicleService(repo)


def get_source_repo(session: AsyncSession = Depends(get_db)) -> ISourceRepository:
    return PostgresSourceRepository(session)


def get_source_service(
    repo: ISourceRepository = Depends(get_source_repo),
    vehicle_repo: IVehicleRepository = Depends(get_vehicle_repo),
) -> SourceService:
    return SourceService(repo, vehicle_repo)
