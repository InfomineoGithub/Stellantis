from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.exceptions import (
    SourceAlreadyExistsError,
    SourceNotFoundError,
    VehicleNotFoundError,
    VehicleSourceLinkError,
)
from app.domain.source import CreateSourceInput, Source, UpdateSourceInput
from app.domain.vehicle import Vehicle
from app.domain_dependencies import get_source_service
from app.services.source_service import SourceService

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("", response_model=Source, status_code=status.HTTP_201_CREATED)
async def create_source(
    input: CreateSourceInput,
    service: SourceService = Depends(get_source_service),
) -> Source:
    try:
        return await service.create(input)
    except SourceAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[Source])
async def list_sources(
    service: SourceService = Depends(get_source_service),
) -> list[Source]:
    return await service.list()


@router.get("/{id}", response_model=Source)
async def get_source(
    id: UUID,
    service: SourceService = Depends(get_source_service),
) -> Source:
    try:
        return await service.get(id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{id}", response_model=Source)
async def update_source(
    id: UUID,
    input: UpdateSourceInput,
    service: SourceService = Depends(get_source_service),
) -> Source:
    try:
        return await service.update(id, input)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SourceAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    id: UUID,
    service: SourceService = Depends(get_source_service),
) -> None:
    try:
        await service.delete(id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def link_vehicle(
    id: UUID,
    vehicle_id: UUID,
    service: SourceService = Depends(get_source_service),
) -> None:
    try:
        await service.link_vehicle(id, vehicle_id)
    except (SourceNotFoundError, VehicleNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VehicleSourceLinkError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{id}/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_vehicle(
    id: UUID,
    vehicle_id: UUID,
    service: SourceService = Depends(get_source_service),
) -> None:
    try:
        await service.unlink_vehicle(id, vehicle_id)
    except (SourceNotFoundError, VehicleSourceLinkError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{id}/vehicles", response_model=list[Vehicle])
async def get_vehicles_for_source(
    id: UUID,
    service: SourceService = Depends(get_source_service),
) -> list[Vehicle]:
    try:
        return await service.get_vehicles_for_source(id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
