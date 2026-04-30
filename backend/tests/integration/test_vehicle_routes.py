import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.domain_dependencies import get_source_repo, get_vehicle_repo, get_vehicle_service
from app.gateway.app import app
from app.services.vehicle_service import VehicleService
from tests.fakes.source_repository import InMemorySourceRepository
from tests.fakes.vehicle_repository import InMemoryVehicleRepository
from tests.integration.conftest import auth_headers


@pytest.fixture(autouse=True)
def override_repos():
    vehicle_repo = InMemoryVehicleRepository()
    source_repo = InMemorySourceRepository()
    app.dependency_overrides[get_vehicle_repo] = lambda: vehicle_repo
    app.dependency_overrides[get_source_repo] = lambda: source_repo
    app.dependency_overrides[get_vehicle_service] = lambda: VehicleService(vehicle_repo)
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(),
    ) as c:
        yield c


CREATE_PAYLOAD = {
    "manufacturer": "Toyota",
    "model_name": "Camry",
    "vehicle_class": "midsize",
    "year": 2024,
    "body_type": "sedan",
    "transmission": "automatic",
    "fuel_type": "gasoline",
}


@pytest.mark.asyncio
async def test_create_vehicle_returns_201(client):
    resp = await client.post("/api/vehicles", json=CREATE_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["manufacturer"] == "Toyota"


@pytest.mark.asyncio
async def test_create_vehicle_duplicate_returns_409(client):
    await client.post("/api/vehicles", json=CREATE_PAYLOAD)
    resp = await client.post("/api/vehicles", json=CREATE_PAYLOAD)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_vehicles_returns_200(client):
    await client.post("/api/vehicles", json=CREATE_PAYLOAD)
    resp = await client.get("/api/vehicles")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_vehicle_not_found_returns_404(client):
    from uuid import uuid4

    resp = await client.get(f"/api/vehicles/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_vehicle_returns_200(client):
    create_resp = await client.post("/api/vehicles", json=CREATE_PAYLOAD)
    vid = create_resp.json()["id"]
    resp = await client.patch(f"/api/vehicles/{vid}", json={"model_name": "Corolla"})
    assert resp.status_code == 200
    assert resp.json()["model_name"] == "Corolla"


@pytest.mark.asyncio
async def test_delete_vehicle_returns_204(client):
    create_resp = await client.post("/api/vehicles", json=CREATE_PAYLOAD)
    vid = create_resp.json()["id"]
    resp = await client.delete(f"/api/vehicles/{vid}")
    assert resp.status_code == 204
