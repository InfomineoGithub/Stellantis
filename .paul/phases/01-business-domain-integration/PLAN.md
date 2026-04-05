# Phase 1: Business Domain Integration — PLAN

## Goal

Establish the clean architecture foundation for the two core domain entities: **Vehicle** and **Source**, including their many-to-many relationship. This phase delivers a fully testable, DB-agnostic domain layer, a PostgreSQL-backed infrastructure layer, a service layer with business rules, REST API endpoints, and a React Query-based frontend data layer. No UI is implemented — only the data contracts, hooks, and utilities that future UI phases will consume.

---

## Scope

### In scope

- Domain models: `Vehicle`, `Source` (pure Pydantic `BaseModel`)
- Enums: `VehicleClass`, `BodyType`, `Transmission`, `FuelType`, `SourceType`
- Domain exceptions: `VehicleAlreadyExistsError`, `VehicleNotFoundError`, `SourceAlreadyExistsError`, `SourceNotFoundError`, `VehicleSourceLinkError`
- Repository protocols: `IVehicleRepository`, `ISourceRepository`
- Infrastructure: async SQLAlchemy `DeclarativeBase` models, `AsyncEngine`, `AsyncSessionLocal`
- Association table: `vehicle_sources` (many-to-many join table)
- Unique constraint: `(manufacturer, model_name, year)` on vehicles table
- Alembic setup with async-compatible `env.py`, initial migration
- Concrete repositories: `PostgresVehicleRepository`, `PostgresSourceRepository`
- In-memory test fakes: `InMemoryVehicleRepository`, `InMemorySourceRepository`
- Services: `VehicleService`, `SourceService`
- FastAPI dependency injection wiring
- FastAPI routers: `/vehicles`, `/sources`
- Unit tests (service logic via in-memory repos)
- Integration tests (API routes via `dependency_overrides`)
- Frontend core module: `vehicles` (types, api, keys, hooks)
- Frontend core module: `sources` (types, api, keys, hooks)

### Out of scope

- Parameters, Runs, Findings — later phases
- Agent integration — later phases
- UI components — later phases
- Use cases (business domain actions like "fetch parameters for a vehicle") — later phases
- RAG / document source processing
- Crawling, scraping, fetching logic on sources

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI Routes                    │
│            /vehicles  /sources                      │
└────────────────────┬────────────────────────────────┘
                     │ Depends()
┌────────────────────▼────────────────────────────────┐
│              Dependencies (DI wiring)               │
│   get_db → get_vehicle_repo → get_vehicle_service   │
│   get_db → get_source_repo  → get_source_service    │
└────────────────────┬────────────────────────────────┘
                     │ injects IVehicleRepository / ISourceRepository
┌────────────────────▼────────────────────────────────┐
│                    Services                         │
│         VehicleService | SourceService              │
│  (business rules: uniqueness, link/unlink logic,    │
│   IntegrityError → domain exception translation)    │
└────────────────────┬────────────────────────────────┘
                     │ IVehicleRepository / ISourceRepository (Protocol)
┌────────────────────▼────────────────────────────────┐
│           Concrete Repositories (Postgres)          │
│  PostgresVehicleRepository | PostgresSourceRepository│
│  (translates domain ↔ infrastructure models,        │
│   owns eager loading strategy per method)           │
└────────────────────┬────────────────────────────────┘
                     │ AsyncSession
┌────────────────────▼────────────────────────────────┐
│         Infrastructure (SQLAlchemy + asyncpg)       │
│    VehicleTable | SourceTable | vehicle_sources      │
│           AsyncEngine | AsyncSessionLocal            │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                  PostgreSQL                         │
└─────────────────────────────────────────────────────┘
```

**Domain layer** (Pydantic `BaseModel`) is fully independent — no SQLAlchemy imports, no DB awareness. All other layers depend inward toward the domain, never the reverse.

---

## Directory Structure

### Backend

```
backend/app/
  domain/
    vehicle.py          # Vehicle domain model + enums (VehicleClass, BodyType, Transmission, FuelType)
    source.py           # Source domain model + SourceType enum
    exceptions.py       # All domain exceptions
    repositories.py     # IVehicleRepository, ISourceRepository protocols

  infrastructure/
    database.py         # AsyncEngine, AsyncSessionLocal, Base (DeclarativeBase)
    models/
      vehicle.py        # VehicleTable (DeclarativeBase, table="vehicles")
      source.py         # SourceTable (DeclarativeBase, table="sources")
      associations.py   # vehicle_sources Table (association, no mapped class)
    repositories/
      vehicle_repository.py   # PostgresVehicleRepository
      source_repository.py    # PostgresSourceRepository

  services/
    vehicle_service.py  # VehicleService
    source_service.py   # SourceService

  dependencies.py       # FastAPI Depends() wiring (get_db, get_*_repo, get_*_service)

  routers/
    vehicles.py         # CRUD routes for /vehicles
    sources.py          # CRUD routes for /sources

alembic/
  env.py                # Async-compatible Alembic env (run_sync pattern)
  versions/
    001_initial_vehicles_sources.py

backend/tests/
  fakes/
    vehicle_repository.py   # InMemoryVehicleRepository
    source_repository.py    # InMemorySourceRepository
  unit/
    test_vehicle_service.py
    test_source_service.py
  integration/
    test_vehicle_routes.py
    test_source_routes.py
```

### Frontend

```
frontend/src/core/
  vehicles/
    types.ts    # Vehicle, CreateVehicleInput, UpdateVehicleInput, VehicleClass, BodyType, Transmission, FuelType
    keys.ts     # vehicleKeys query key factory
    api.ts      # raw fetchWithAuth calls
    hooks.ts    # useVehicles, useVehicle, useVehicleWithSources, useCreateVehicle, useUpdateVehicle, useDeleteVehicle
  sources/
    types.ts    # Source, CreateSourceInput, UpdateSourceInput, SourceType
    keys.ts     # sourceKeys query key factory
    api.ts      # raw fetchWithAuth calls
    hooks.ts    # useSources, useSource, useCreateSource, useUpdateSource, useDeleteSource, useSourceVehicles, useLinkVehicle, useUnlinkVehicle
```

---

## Domain Specification

### Enums

```python
class VehicleClass(str, Enum):
    compact   = "compact"
    midsize   = "midsize"
    full_size = "full_size"
    luxury    = "luxury"
    economy   = "economy"

class BodyType(str, Enum):
    sedan       = "sedan"
    suv         = "suv"
    hatchback   = "hatchback"
    coupe       = "coupe"
    convertible = "convertible"
    pickup      = "pickup"
    van         = "van"

class Transmission(str, Enum):
    manual    = "manual"
    automatic = "automatic"
    cvt       = "cvt"

class FuelType(str, Enum):
    gasoline = "gasoline"
    diesel   = "diesel"
    electric = "electric"
    hybrid   = "hybrid"
    phev     = "phev"
    bev      = "bev"

class SourceType(str, Enum):
    web_url       = "web_url"
    youtube_video = "youtube_video"
    pdf           = "pdf"
```

No `other` catch-all. Enums are extended by adding new members. Existing rows are not affected.

### Vehicle domain model

```python
class Vehicle(BaseModel):
    id:            UUID
    manufacturer:  str
    model_name:    str
    vehicle_class: VehicleClass
    year:          int                      # e.g. 2024
    body_type:     BodyType
    transmission:  Transmission
    fuel_type:     FuelType
    thumbnail_url: str | None = None        # optional display image
    notes:         str | None = None        # freeform context (e.g. trim level, special edition)
    created_at:    datetime
    updated_at:    datetime
    sources:       list[Source] | None = None  # None = not loaded, [] = loaded but empty
```

**Uniqueness rule:** `(manufacturer, model_name, year)` must be unique across all vehicles.

### Source domain model

```python
class Source(BaseModel):
    id:          UUID
    source_type: SourceType
    url:         str
    description: str | None = None
    is_active:   bool = True               # marks stale/broken sources
    created_at:  datetime
    updated_at:  datetime
```

Source has no `vehicles` field in the domain model. The vehicle-source relationship is navigated via `Vehicle.sources` only. At the SQLAlchemy level, `SourceTable` has a `vehicles` back-relationship for internal querying, but this does not surface in the domain.

### Domain exceptions

```python
# domain/exceptions.py

class VehicleAlreadyExistsError(Exception):
    """Raised when (manufacturer, model_name, year) already exists."""

class VehicleNotFoundError(Exception):
    """Raised when a vehicle with the given ID does not exist."""

class SourceAlreadyExistsError(Exception):
    """Raised when a source with the same URL already exists."""

class SourceNotFoundError(Exception):
    """Raised when a source with the given ID does not exist."""

class VehicleSourceLinkError(Exception):
    """Raised when a vehicle-source link operation fails (already linked, not linked, etc.)."""
```

Routes catch domain exceptions and map to HTTP responses. SQLAlchemy `IntegrityError` never reaches the route layer.

---

## Repository Protocols

```python
# domain/repositories.py

class IVehicleRepository(Protocol):
    async def add(self, vehicle: Vehicle) -> Vehicle: ...
    async def get(self, id: UUID) -> Vehicle | None: ...
    async def get_with_sources(self, id: UUID) -> Vehicle | None: ...
    async def list(self) -> list[Vehicle]: ...
    async def update(self, vehicle: Vehicle) -> Vehicle: ...
    async def delete(self, id: UUID) -> None: ...

class ISourceRepository(Protocol):
    async def add(self, source: Source) -> Source: ...
    async def get(self, id: UUID) -> Source | None: ...
    async def list(self) -> list[Source]: ...
    async def update(self, source: Source) -> Source: ...
    async def delete(self, id: UUID) -> None: ...
    async def link_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None: ...
    async def unlink_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None: ...
    async def get_vehicles_for_source(self, source_id: UUID) -> list[Vehicle]: ...
```

`get` returns `Vehicle` with `sources=None` (relationship not loaded).
`get_with_sources` returns `Vehicle` with `sources: list[Source]` (eagerly loaded via `selectinload`).

`SourceRepository` owns the many-to-many join table (`vehicle_sources`). It is the sole writer for link/unlink operations. `VehicleRepository.get_with_sources` reads the relationship via SQLAlchemy's `selectinload` but never writes to the join table.

---

## Infrastructure Specification

### Database setup (`infrastructure/database.py`)

```python
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = DeclarativeBase()
```

`DATABASE_URL` uses `postgresql+asyncpg://` scheme. Loaded from environment/config.

### VehicleTable (`infrastructure/models/vehicle.py`)

Columns: `id (UUID PK)`, `manufacturer`, `model_name`, `vehicle_class (Enum)`, `year`, `body_type (Enum)`, `transmission (Enum)`, `fuel_type (Enum)`, `thumbnail_url (nullable)`, `notes (nullable)`, `created_at`, `updated_at`.

Unique constraint: `UniqueConstraint("manufacturer", "model_name", "year")`.

Relationship: `sources` → `SourceTable` via `secondary=vehicle_sources`, `back_populates="vehicles"`, `lazy="noload"` (explicit — never auto-loaded).

### SourceTable (`infrastructure/models/source.py`)

Columns: `id (UUID PK)`, `source_type (Enum)`, `url (unique)`, `description (nullable)`, `is_active (Boolean, default True)`, `created_at`, `updated_at`.

Relationship: `vehicles` → `VehicleTable` via `secondary=vehicle_sources`, `back_populates="sources"`, `lazy="noload"`.

### Association table (`infrastructure/models/associations.py`)

```python
vehicle_sources = Table(
    "vehicle_sources",
    Base.metadata,
    Column("vehicle_id", UUID, ForeignKey("vehicles.id"), primary_key=True),
    Column("source_id",  UUID, ForeignKey("sources.id"),  primary_key=True),
)
```

No mapped class. No repository. Managed entirely through SQLAlchemy relationship operations in `PostgresSourceRepository`.

### Repository implementation pattern

Each repository method:
1. Accepts domain model(s) or primitive IDs
2. Translates to/from SQLAlchemy model via private `_to_domain()` and `_to_table()` methods
3. Executes async SQLAlchemy query
4. Returns domain model(s)
5. Never calls `session.commit()` — session lifecycle owned by FastAPI dependency

`get` uses plain `select(VehicleTable).where(...)` — no `selectinload`.
`get_with_sources` uses `select(VehicleTable).options(selectinload(VehicleTable.sources)).where(...)`.

`IntegrityError` from SQLAlchemy is caught inside the repository and re-raised as the appropriate domain exception.

---

## Service Specification

### VehicleService

```python
class VehicleService:
    def __init__(self, repo: IVehicleRepository): ...

    async def create(self, input: CreateVehicleInput) -> Vehicle:
        # 1. Check uniqueness: repo.get_by_manufacturer_model_year() or catch IntegrityError
        # 2. Build Vehicle domain model with new UUID + timestamps
        # 3. repo.add(vehicle)
        # Raises: VehicleAlreadyExistsError

    async def get(self, id: UUID) -> Vehicle:
        # repo.get(id) → raise VehicleNotFoundError if None

    async def get_with_sources(self, id: UUID) -> Vehicle:
        # repo.get_with_sources(id) → raise VehicleNotFoundError if None

    async def list(self) -> list[Vehicle]:
        # repo.list()

    async def update(self, id: UUID, input: UpdateVehicleInput) -> Vehicle:
        # get → apply changes → repo.update()
        # Raises: VehicleNotFoundError, VehicleAlreadyExistsError (if new name/year collides)

    async def delete(self, id: UUID) -> None:
        # get → repo.delete()
        # Raises: VehicleNotFoundError
```

### SourceService

```python
class SourceService:
    def __init__(self, repo: ISourceRepository): ...

    async def create(self, input: CreateSourceInput) -> Source:
        # Build Source with new UUID + timestamps → repo.add()
        # Raises: SourceAlreadyExistsError (duplicate URL)

    async def get(self, id: UUID) -> Source:
        # repo.get(id) → raise SourceNotFoundError if None

    async def list(self) -> list[Source]:
        # repo.list()

    async def update(self, id: UUID, input: UpdateSourceInput) -> Source:
        # get → apply changes → repo.update()
        # Raises: SourceNotFoundError, SourceAlreadyExistsError

    async def delete(self, id: UUID) -> None:
        # get → repo.delete()
        # Raises: SourceNotFoundError

    async def link_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None:
        # Validate both exist → repo.link_vehicle()
        # Raises: SourceNotFoundError, VehicleNotFoundError, VehicleSourceLinkError (already linked)

    async def unlink_vehicle(self, source_id: UUID, vehicle_id: UUID) -> None:
        # Validate both exist → repo.unlink_vehicle()
        # Raises: SourceNotFoundError, VehicleNotFoundError, VehicleSourceLinkError (not linked)

    async def get_vehicles_for_source(self, source_id: UUID) -> list[Vehicle]:
        # get → repo.get_vehicles_for_source()
        # Raises: SourceNotFoundError
```

---

## FastAPI Dependency Wiring

```python
# dependencies.py

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        async with session.begin():   # auto-commit on success, rollback on exception
            yield session

def get_vehicle_repo(session: AsyncSession = Depends(get_db)) -> IVehicleRepository:
    return PostgresVehicleRepository(session)

def get_vehicle_service(repo: IVehicleRepository = Depends(get_vehicle_repo)) -> VehicleService:
    return VehicleService(repo)

def get_source_repo(session: AsyncSession = Depends(get_db)) -> ISourceRepository:
    return PostgresSourceRepository(session)

def get_source_service(repo: ISourceRepository = Depends(get_source_repo)) -> SourceService:
    return SourceService(repo)
```

Services are **never** singletons. A new instance is created per request with the request-scoped session. This ensures no session leakage across requests.

---

## API Routes

### Vehicle routes (`/vehicles`)

| Method | Path | Description | Success | Error |
|--------|------|-------------|---------|-------|
| POST | `/vehicles` | Create vehicle | 201 + Vehicle | 409 if duplicate |
| GET | `/vehicles` | List all vehicles | 200 + list | — |
| GET | `/vehicles/{id}` | Get vehicle (no sources) | 200 + Vehicle | 404 |
| GET | `/vehicles/{id}/with-sources` | Get vehicle with sources | 200 + Vehicle | 404 |
| PATCH | `/vehicles/{id}` | Update vehicle | 200 + Vehicle | 404, 409 |
| DELETE | `/vehicles/{id}` | Delete vehicle | 204 | 404 |

### Source routes (`/sources`)

| Method | Path | Description | Success | Error |
|--------|------|-------------|---------|-------|
| POST | `/sources` | Create source | 201 + Source | 409 if duplicate URL |
| GET | `/sources` | List all sources | 200 + list | — |
| GET | `/sources/{id}` | Get source | 200 + Source | 404 |
| PATCH | `/sources/{id}` | Update source | 200 + Source | 404, 409 |
| DELETE | `/sources/{id}` | Delete source | 204 | 404 |
| POST | `/sources/{id}/vehicles/{vehicle_id}` | Link vehicle to source | 204 | 404, 409 |
| DELETE | `/sources/{id}/vehicles/{vehicle_id}` | Unlink vehicle from source | 204 | 404 |
| GET | `/sources/{id}/vehicles` | Get vehicles for source | 200 + list | 404 |

---

## Alembic Setup

Alembic must be configured for async SQLAlchemy. The default template does not support this.

`alembic/env.py` must use the `run_sync` pattern:

```python
def run_migrations_online():
    connectable = create_async_engine(DATABASE_URL)

    async def run_async_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(run_async_migrations())
```

Initial migration (`001_initial_vehicles_sources.py`) creates:
- `vehicles` table with all columns and enums
- `sources` table with all columns and enums
- `vehicle_sources` association table
- `UniqueConstraint("manufacturer", "model_name", "year")` on `vehicles`
- `UniqueConstraint("url")` on `sources`

Alembic is run via `alembic upgrade head`. This must be documented in the backend `Makefile` or `README`.

---

## Testing Strategy

### Level 1 — Unit tests (no DB, no HTTP)

Use `InMemoryVehicleRepository` and `InMemorySourceRepository` — concrete implementations of the protocols backed by Python dicts. Instantiate services directly.

Cover:
- `VehicleService.create` — happy path
- `VehicleService.create` — duplicate raises `VehicleAlreadyExistsError`
- `VehicleService.get` — not found raises `VehicleNotFoundError`
- `VehicleService.update` — happy path
- `VehicleService.delete` — happy path
- `SourceService.link_vehicle` — happy path
- `SourceService.link_vehicle` — already linked raises `VehicleSourceLinkError`
- `SourceService.unlink_vehicle` — not linked raises `VehicleSourceLinkError`

### Level 2 — Integration tests (FastAPI + in-memory repo, no DB)

Use `httpx.AsyncClient` + `app.dependency_overrides` to swap Postgres repos for in-memory.

Cover all API routes: status codes, response shape, error responses (404, 409).

```python
@pytest.fixture(autouse=True)
def override_repos():
    app.dependency_overrides[get_vehicle_repo] = lambda: InMemoryVehicleRepository()
    app.dependency_overrides[get_source_repo]  = lambda: InMemorySourceRepository()
    yield
    app.dependency_overrides.clear()
```

### Level 3 — E2E (real DB) — deferred to CI

Not required in this phase. Will be added when test database provisioning is set up in CI.

---

## Frontend Specification

### Vehicle module (`src/core/vehicles/`)

**`types.ts`**
```typescript
export type VehicleClass = 'compact' | 'midsize' | 'full_size' | 'luxury' | 'economy'
export type BodyType     = 'sedan' | 'suv' | 'hatchback' | 'coupe' | 'convertible' | 'pickup' | 'van'
export type Transmission = 'manual' | 'automatic' | 'cvt'
export type FuelType     = 'gasoline' | 'diesel' | 'electric' | 'hybrid' | 'phev' | 'bev'

export interface Vehicle {
  id:            string
  manufacturer:  string
  model_name:    string
  vehicle_class: VehicleClass
  year:          number
  body_type:     BodyType
  transmission:  Transmission
  fuel_type:     FuelType
  thumbnail_url: string | null
  notes:         string | null
  created_at:    string
  updated_at:    string
  sources?:      Source[]         // present only when fetched with-sources
}

export interface CreateVehicleInput {
  manufacturer:  string
  model_name:    string
  vehicle_class: VehicleClass
  year:          number
  body_type:     BodyType
  transmission:  Transmission
  fuel_type:     FuelType
  thumbnail_url?: string
  notes?:        string
}

export interface UpdateVehicleInput extends Partial<CreateVehicleInput> {}
```

**`keys.ts`** — React Query key factory
```typescript
export const vehicleKeys = {
  all:         () => ['vehicles'] as const,
  lists:       () => [...vehicleKeys.all(), 'list'] as const,
  detail:      (id: string) => [...vehicleKeys.all(), 'detail', id] as const,
  withSources: (id: string) => [...vehicleKeys.detail(id), 'with-sources'] as const,
}
```

**`api.ts`** — raw fetch functions (using `fetchWithAuth`)

Functions: `fetchVehicles()`, `fetchVehicle(id)`, `fetchVehicleWithSources(id)`, `createVehicle(input)`, `updateVehicle(id, input)`, `deleteVehicle(id)`.

**`hooks.ts`** — React Query hooks

- `useVehicles()` — `useQuery` on `vehicleKeys.lists()`
- `useVehicle(id)` — `useQuery` on `vehicleKeys.detail(id)`
- `useVehicleWithSources(id)` — `useQuery` on `vehicleKeys.withSources(id)`
- `useCreateVehicle()` — `useMutation`, invalidates `vehicleKeys.lists()` on success
- `useUpdateVehicle()` — `useMutation`, invalidates `vehicleKeys.detail(id)` and `vehicleKeys.lists()` on success
- `useDeleteVehicle()` — `useMutation`, invalidates `vehicleKeys.lists()` on success

### Source module (`src/core/sources/`)

**`types.ts`**
```typescript
export type SourceType = 'web_url' | 'youtube_video' | 'pdf'

export interface Source {
  id:          string
  source_type: SourceType
  url:         string
  description: string | null
  is_active:   boolean
  created_at:  string
  updated_at:  string
}

export interface CreateSourceInput {
  source_type:  SourceType
  url:          string
  description?: string
  is_active?:   boolean
}

export interface UpdateSourceInput extends Partial<CreateSourceInput> {}
```

**`keys.ts`**
```typescript
export const sourceKeys = {
  all:      () => ['sources'] as const,
  lists:    () => [...sourceKeys.all(), 'list'] as const,
  detail:   (id: string) => [...sourceKeys.all(), 'detail', id] as const,
  vehicles: (id: string) => [...sourceKeys.detail(id), 'vehicles'] as const,
}
```

**`api.ts`** — Functions: `fetchSources()`, `fetchSource(id)`, `createSource(input)`, `updateSource(id, input)`, `deleteSource(id)`, `fetchSourceVehicles(id)`, `linkVehicleToSource(sourceId, vehicleId)`, `unlinkVehicleFromSource(sourceId, vehicleId)`.

**`hooks.ts`**
- `useSources()` — `useQuery` on `sourceKeys.lists()`
- `useSource(id)` — `useQuery` on `sourceKeys.detail(id)`
- `useCreateSource()` — `useMutation`, invalidates `sourceKeys.lists()`
- `useUpdateSource()` — `useMutation`, invalidates `sourceKeys.detail(id)` and `sourceKeys.lists()`
- `useDeleteSource()` — `useMutation`, invalidates `sourceKeys.lists()`
- `useSourceVehicles(id)` — `useQuery` on `sourceKeys.vehicles(id)`
- `useLinkVehicle()` — `useMutation`, invalidates `sourceKeys.vehicles(sourceId)` and `vehicleKeys.withSources(vehicleId)`
- `useUnlinkVehicle()` — `useMutation`, invalidates same

---

## Task Breakdown

### Backend tasks (independent — can be parallelized)

| ID | Task | Depends on | Notes |
|----|------|-----------|-------|
| B1 | Create `backend/app/domain/` with `vehicle.py`, `source.py`, `exceptions.py`, `repositories.py` | — | Pure Python, no dependencies |
| B2 | Create `backend/app/infrastructure/database.py` (engine, session, Base) | — | Needs DB URL from config |
| B3 | Create `backend/app/infrastructure/models/` (VehicleTable, SourceTable, associations) | B2 | Depends on Base |
| B4 | Configure Alembic with async `env.py` | B2, B3 | Generate initial migration after |
| B5 | Create `backend/tests/fakes/` (InMemoryVehicleRepository, InMemorySourceRepository) | B1 | Implements protocols from B1 |
| B6 | Create `backend/app/infrastructure/repositories/` (PostgresVehicleRepository, PostgresSourceRepository) | B1, B3 | Implements protocols, translates domain ↔ table |
| B7 | Create `backend/app/services/` (VehicleService, SourceService) | B1 | Depends on protocols only |
| B8 | Create `backend/app/dependencies.py` | B6, B7 | Wires DI |
| B9 | Create `backend/app/routers/` (vehicles.py, sources.py) | B7, B8 | Routes call services |
| B10 | Write unit tests (`tests/unit/`) | B5, B7 | No DB needed |
| B11 | Write integration tests (`tests/integration/`) | B8, B9, B5 | Uses dependency_overrides |

### Frontend tasks (independent of backend tasks)

| ID | Task | Depends on | Notes |
|----|------|-----------|-------|
| F1 | Create `src/core/vehicles/types.ts` | — | Mirror backend enums exactly |
| F2 | Create `src/core/vehicles/keys.ts` | — | Pure constants |
| F3 | Create `src/core/vehicles/api.ts` | F1 | Uses fetchWithAuth |
| F4 | Create `src/core/vehicles/hooks.ts` | F1, F2, F3 | React Query hooks |
| F5 | Create `src/core/sources/types.ts` | F1 | Source references Vehicle type |
| F6 | Create `src/core/sources/keys.ts` | — | |
| F7 | Create `src/core/sources/api.ts` | F5 | |
| F8 | Create `src/core/sources/hooks.ts` | F5, F6, F7 | Includes link/unlink mutations |

---

## Acceptance Criteria

- [ ] `Vehicle` and `Source` domain models defined as pure Pydantic `BaseModel` with no SQLAlchemy imports
- [ ] All enums defined without `other` catch-all
- [ ] All domain exceptions defined and documented
- [ ] `IVehicleRepository` and `ISourceRepository` protocols defined
- [ ] `VehicleTable`, `SourceTable`, `vehicle_sources` defined with `DeclarativeBase`
- [ ] Unique constraint on `(manufacturer, model_name, year)` in schema
- [ ] Unique constraint on `url` in sources schema
- [ ] Alembic initialized with async `env.py`; `alembic upgrade head` runs without error
- [ ] `PostgresVehicleRepository` implements `IVehicleRepository`; `get` returns `sources=None`, `get_with_sources` returns loaded sources
- [ ] `PostgresSourceRepository` implements `ISourceRepository`; owns link/unlink
- [ ] `InMemoryVehicleRepository` and `InMemorySourceRepository` implement the same protocols
- [ ] `VehicleService` raises `VehicleAlreadyExistsError` on duplicate, `VehicleNotFoundError` on missing
- [ ] `SourceService` raises `SourceAlreadyExistsError` on duplicate URL, `VehicleSourceLinkError` on already-linked/not-linked
- [ ] FastAPI `dependency_overrides` pattern wired; services never import concrete repos
- [ ] All API routes return correct status codes per table above
- [ ] All unit tests pass (`pytest tests/unit/`)
- [ ] All integration tests pass (`pytest tests/integration/`)
- [ ] Frontend: `vehicleKeys`, `sourceKeys` factories cover all query variants
- [ ] Frontend: all mutations invalidate the correct query keys on success
- [ ] Frontend: type definitions match backend response shapes exactly
- [ ] `pnpm check` passes (lint + type check)

---

*PLAN.md — Phase 1: Business Domain Integration*
*Created: 2026-04-05*
