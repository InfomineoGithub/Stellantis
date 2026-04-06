import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.domain_dependencies import get_source_repo, get_source_service, get_vehicle_repo
from app.gateway.app import app
from app.services.source_service import SourceService
from tests.fakes.source_repository import InMemorySourceRepository
from tests.fakes.vehicle_repository import InMemoryVehicleRepository


@pytest.fixture(autouse=True)
def override_repos():
    vehicle_repo = InMemoryVehicleRepository()
    source_repo = InMemorySourceRepository()
    app.dependency_overrides[get_vehicle_repo] = lambda: vehicle_repo
    app.dependency_overrides[get_source_repo] = lambda: source_repo
    app.dependency_overrides[get_source_service] = lambda: SourceService(source_repo, vehicle_repo)
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


CREATE_SOURCE = {"source_type": "web_url", "url": "https://example.com"}


@pytest.mark.asyncio
async def test_create_source_returns_201(client):
    resp = await client.post("/api/sources", json=CREATE_SOURCE)
    assert resp.status_code == 201
    assert resp.json()["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_create_source_duplicate_returns_409(client):
    await client.post("/api/sources", json=CREATE_SOURCE)
    resp = await client.post("/api/sources", json=CREATE_SOURCE)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_sources_returns_200(client):
    await client.post("/api/sources", json=CREATE_SOURCE)
    resp = await client.get("/api/sources")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_source_not_found_returns_404(client):
    from uuid import uuid4

    resp = await client.get(f"/api/sources/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_source_returns_204(client):
    create_resp = await client.post("/api/sources", json=CREATE_SOURCE)
    sid = create_resp.json()["id"]
    resp = await client.delete(f"/api/sources/{sid}")
    assert resp.status_code == 204
