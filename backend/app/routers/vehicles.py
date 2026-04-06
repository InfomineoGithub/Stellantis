from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.exceptions import VehicleAlreadyExistsError, VehicleNotFoundError
from app.domain.vehicle import CreateVehicleInput, UpdateVehicleInput, Vehicle
from app.domain_dependencies import get_vehicle_service
from app.services.vehicle_service import VehicleService

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


@router.post("", response_model=Vehicle, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    input: CreateVehicleInput,
    service: VehicleService = Depends(get_vehicle_service),
) -> Vehicle:
    try:
        return await service.create(input)
    except VehicleAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[Vehicle])
async def list_vehicles(
    service: VehicleService = Depends(get_vehicle_service),
) -> list[Vehicle]:
    return await service.list()


@router.get("/{id}", response_model=Vehicle)
async def get_vehicle(
    id: UUID,
    service: VehicleService = Depends(get_vehicle_service),
) -> Vehicle:
    try:
        return await service.get(id)
    except VehicleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{id}/with-sources", response_model=Vehicle)
async def get_vehicle_with_sources(
    id: UUID,
    service: VehicleService = Depends(get_vehicle_service),
) -> Vehicle:
    try:
        return await service.get_with_sources(id)
    except VehicleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{id}", response_model=Vehicle)
async def update_vehicle(
    id: UUID,
    input: UpdateVehicleInput,
    service: VehicleService = Depends(get_vehicle_service),
) -> Vehicle:
    try:
        return await service.update(id, input)
    except VehicleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VehicleAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    id: UUID,
    service: VehicleService = Depends(get_vehicle_service),
) -> None:
    try:
        await service.delete(id)
    except VehicleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
