# Architecture Decision Records — Phase 1: Business Domain Integration

> ADRs capture the architectural decisions made during planning for this phase,
> including context, alternatives considered, and consequences. These are immutable
> records — if a decision changes in a later phase, a new ADR is added rather than
> editing this one.

---

## ADR-001: Clean Architecture with Strict Layer Separation

**Status:** Accepted
**Date:** 2026-04-05

### Context

The platform needs to persist automotive domain data (vehicles, sources) to PostgreSQL. We need to decide how to structure the code: whether to couple business logic tightly to the database ORM or to maintain independence between layers.

### Decision

Adopt clean architecture with four distinct layers, each with a strict dependency direction (inward only):

```
Routes → Services → Repository Protocols → (Infrastructure implements protocols)
                                         → (Domain is imported by all layers)
```

1. **Domain layer** — pure Python, zero framework imports
2. **Repository protocols** — abstract interfaces, defined in domain layer
3. **Services** — business logic, depend only on protocols
4. **Infrastructure** — concrete implementations (SQLAlchemy, Postgres)

No layer may import from a layer further out than itself. Domain has no imports from SQLAlchemy, FastAPI, or infrastructure.

### Alternatives considered

- **Active Record / ORM-coupled approach:** Models are SQLAlchemy classes used directly in business logic. Simpler initially but creates tight coupling — testing requires a real DB, swapping the DB is a full rewrite, and business logic becomes entangled with persistence concerns.
- **Partial separation (service + ORM models):** Services exist but operate on SQLAlchemy models directly. Reduces boilerplate but still ties business logic to ORM lifecycle (sessions, lazy loading, detached instances).

### Consequences

- **Positive:** Services are testable without a DB. Repository implementations can be swapped (Postgres today, another store later). Domain logic is readable without understanding ORM.
- **Negative:** Translation layer between domain and infrastructure models adds boilerplate. Every new entity requires two model definitions (domain + infrastructure) and mapper methods.
- **Accepted trade-off:** Boilerplate is mechanical and consistent. The testability and decoupling benefits outweigh the verbosity at this scale.

---

## ADR-002: SQLAlchemy DeclarativeBase for Infrastructure Models (not SQLModel)

**Status:** Accepted
**Date:** 2026-04-05

### Context

The Python ecosystem offers several ORM options for PostgreSQL. The initial assumption was to use SQLModel (a SQLAlchemy + Pydantic hybrid), but this conflicts with the clean architecture decision (ADR-001).

### Decision

Use plain SQLAlchemy `DeclarativeBase` for infrastructure models. Domain models are separate pure Pydantic `BaseModel` classes. Translation between the two is handled by private mapper methods inside each repository (`_to_domain()`, `_to_table()`).

```python
# Infrastructure model (SQLAlchemy)
class VehicleTable(Base):
    __tablename__ = "vehicles"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    ...

# Domain model (Pydantic)
class Vehicle(BaseModel):
    id: UUID
    ...
```

### Alternatives considered

- **SQLModel:** Combines SQLAlchemy table and Pydantic schema into one class. Eliminates the translation layer. However, it blurs the domain/infrastructure boundary — the same class carries ORM session state and business logic. This undermines the independence goal of ADR-001. SQLModel also has documented friction with async SQLAlchemy that requires workarounds.
- **Tortoise ORM:** Django-style async ORM. Less ecosystem maturity, not compatible with the existing project stack.

### Consequences

- **Positive:** Domain models are completely independent of SQLAlchemy lifecycle. No `DetachedInstanceError`, no lazy-loading surprises in domain objects, no ORM session contamination in business logic.
- **Negative:** Every entity has two class definitions. Mapper methods must be kept in sync manually when fields change.
- **Accepted trade-off:** Field changes are infrequent once the domain is stable. The mapper methods are straightforward and centralized in the repository.

---

## ADR-003: Pure Pydantic BaseModel for Domain Models

**Status:** Accepted
**Date:** 2026-04-05

### Context

Domain models need to represent business entities (Vehicle, Source) in a way that is serializable, validatable, and independent of infrastructure.

### Decision

All domain models extend `pydantic.BaseModel`. No SQLAlchemy mixins, no `table=True`, no ORM-specific fields. Enums are `str, Enum` subclasses (serializable as strings). UUIDs are native Python `uuid.UUID`. Datetimes are `datetime.datetime`.

### Alternatives considered

- **Plain dataclasses:** No validation, no serialization support, no schema generation.
- **SQLModel (Pydantic + SQLAlchemy):** Rejected — see ADR-002.
- **attrs:** Mature but less ecosystem integration compared to Pydantic for FastAPI projects.

### Consequences

- **Positive:** Domain models serialize to JSON naturally. FastAPI can use them directly as response schemas (or thin wrappers). Validation is built in.
- **Negative:** Pydantic v2 has breaking changes from v1 — the project must be consistent on which version is used.
- **Note:** `sources: list[Source] | None = None` on `Vehicle` uses `None` (not `[]`) to distinguish "not loaded" from "has no sources". This is a deliberate signal to callers.

---

## ADR-004: Repository Protocol (Structural Subtyping) over ABC

**Status:** Accepted
**Date:** 2026-04-05

### Context

Repository interfaces need to be defined so that services depend on abstractions, not concrete implementations. Python offers two mechanisms: `abc.ABC` (nominal subtyping) and `typing.Protocol` (structural subtyping).

### Decision

Use `typing.Protocol` to define `IVehicleRepository` and `ISourceRepository`. Concrete implementations (Postgres, in-memory) implement the protocol implicitly — no explicit inheritance required.

```python
class IVehicleRepository(Protocol):
    async def add(self, vehicle: Vehicle) -> Vehicle: ...
    async def get(self, id: UUID) -> Vehicle | None: ...
    ...
```

### Alternatives considered

- **ABC with `@abstractmethod`:** Requires explicit inheritance (`class PostgresVehicleRepository(IVehicleRepository)`). More explicit but couples the infrastructure class to the domain protocol file. Also requires all abstract methods to be implemented or the class cannot be instantiated — stricter.
- **Duck typing (no interface):** No formal protocol. Relies on the developer to ensure method signatures match. No IDE support, no type checker enforcement.

### Consequences

- **Positive:** In-memory fakes and Postgres repositories are decoupled from the protocol definition. Type checkers (mypy, pyright) validate conformance. Swapping implementations requires no inheritance changes.
- **Negative:** Structural subtyping errors are caught at type-check time, not at instantiation time. Requires type checker to be run (`make lint` or CI) to get the safety guarantee.
- **Note:** `runtime_checkable` is not needed unless `isinstance()` checks are used, which they won't be in this architecture.

---

## ADR-005: FastAPI dependency_overrides for Dependency Injection

**Status:** Accepted
**Date:** 2026-04-05

### Context

Services depend on repository protocols (ADR-004). The concrete implementations must be injected at runtime. The project needs a DI mechanism that: (a) creates repositories per-request with the request-scoped session, (b) supports swapping implementations for tests without modifying application code, and (c) integrates naturally with FastAPI.

### Decision

Use FastAPI's built-in `Depends()` system with `dependency_overrides` for test injection. Define a chain of provider functions in `dependencies.py`:

```python
def get_vehicle_repo(session = Depends(get_db)) -> IVehicleRepository:
    return PostgresVehicleRepository(session)

def get_vehicle_service(repo = Depends(get_vehicle_repo)) -> VehicleService:
    return VehicleService(repo)
```

In tests:
```python
app.dependency_overrides[get_vehicle_repo] = lambda: InMemoryVehicleRepository()
```

### Alternatives considered

- **Service locator via config.yaml string resolution:** The existing DeerFlow codebase resolves class names from config strings. Flexible but opaque — the dependency graph is not visible to the type checker or IDE. Hard to trace call paths. Harder to test (requires config mutation).
- **DI container (dependency-injector, punq):** Full DI container libraries. More powerful for complex graphs but adds a dependency and learning curve. FastAPI's native system is sufficient for this scope.
- **Manual instantiation in route handlers:** Direct construction of repos/services in routes. Simple but non-testable without patching.

### Consequences

- **Positive:** Dependency graph is explicit and type-checked. Tests swap implementations with one line per override. No config mutation needed. FastAPI's `TestClient` / `AsyncClient` uses the same override mechanism.
- **Negative:** Services are re-instantiated on every request (not singletons). Acceptable — construction is cheap (just object creation).
- **Testing levels enabled:**
  - Unit: instantiate service directly with fake repo (no FastAPI)
  - Integration: override dependency, hit HTTP routes (no DB)
  - E2E: no override, real DB

---

## ADR-006: Single AsyncSession per Request with Auto-Commit via session.begin()

**Status:** Accepted
**Date:** 2026-04-05

### Context

Multiple repositories may be used within a single request (e.g., `SourceService` validates a vehicle exists before linking it). All operations within a request must share one session to be atomic. The question is: who owns the transaction and when does it commit?

### Decision

The session is created in `get_db()` using `session.begin()` as a context manager. SQLAlchemy auto-commits on clean exit and auto-rolls back on exception. Neither repositories nor services call `commit()` or `rollback()`.

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session
```

The single session is passed through: `get_db → get_vehicle_repo(session) → VehicleService(repo)`. Both `get_vehicle_repo` and `get_source_repo` receive the same session instance via `Depends(get_db)`.

### Alternatives considered

- **Repository-owned commits:** Each repository calls `session.commit()` after mutations. Simpler but breaks atomicity — if two repos are used in one service operation, a failure between the two commits leaves the DB in a partial state.
- **Service-owned commits:** Services call `session.commit()`. More explicit than auto-commit but creates complexity when services call other services. Also mixes infrastructure concerns into service layer.
- **Unit of Work pattern:** Explicit `UnitOfWork` class injected into services. More formal but adds boilerplate without clear benefit over FastAPI's session lifecycle for this scope.

### Consequences

- **Positive:** Atomicity guaranteed across all repository operations in a single request. Services and repositories are free of commit/rollback logic — they're purely domain and data operations.
- **Negative:** Entire request is one transaction. Long-running requests hold the transaction open. Acceptable for the CRUD operations in this phase; revisit if long-running agent operations are added later.
- **Important:** `expire_on_commit=False` is set on `AsyncSessionLocal` to prevent SQLAlchemy from expiring attributes after commit — domain model attributes must remain accessible after the session closes.

---

## ADR-007: UUID Primary Keys

**Status:** Accepted
**Date:** 2026-04-05

### Context

Primary keys can be auto-incrementing integers or UUIDs. The choice has implications for security, distributed systems, and frontend handling.

### Decision

All primary keys use `UUID` (version 4, generated in Python at entity creation time). The database column type is `UUID` (native Postgres UUID type via SQLAlchemy).

UUIDs are generated by the service layer (not the DB) before the domain model is created. This means the ID is known before the insert and can be returned without a DB round-trip to get `lastrowid`.

### Alternatives considered

- **Auto-increment integer:** Simpler, smaller, DB-generated. However, exposes sequential resource IDs in URLs (enumeration attack surface), requires a DB round-trip to get the generated ID, and is harder to distribute across multiple DB nodes in the future.
- **ULID / KSUID:** Sortable UUID alternatives. Better for time-ordered queries. Not chosen — adds a dependency and sortability is not a current requirement.

### Consequences

- **Positive:** IDs are non-enumerable in URLs. Can be generated before DB insert. Globally unique without coordination.
- **Negative:** Larger storage (16 bytes vs 4 bytes for int). Slightly worse index performance for sequential inserts (random UUID fragmentation). Acceptable at this scale.

---

## ADR-008: Alembic for Database Migrations with Async Configuration

**Status:** Accepted
**Date:** 2026-04-05

### Context

The PostgreSQL schema needs a migration system. `Base.metadata.create_all()` is only suitable for development. Production requires versioned, reversible migrations.

### Decision

Use Alembic for all schema migrations. Because the project uses `asyncpg` (async driver), Alembic's `env.py` must be modified to use the `run_sync` pattern — Alembic cannot use async connections natively.

```python
# alembic/env.py
async def run_async_migrations():
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
asyncio.run(run_async_migrations())
```

The initial migration (`001_initial_vehicles_sources.py`) is auto-generated from `Base.metadata` and then reviewed manually before applying.

Migration workflow: `alembic revision --autogenerate -m "description"` → review → `alembic upgrade head`.

### Alternatives considered

- **`create_all()` at startup:** No versioning, no rollback, no history. Not suitable for production.
- **Manually written SQL migrations:** Full control but no autogenerate support. Error-prone and verbose.
- **Aerich (Tortoise ORM migrations):** Not compatible with SQLAlchemy.

### Consequences

- **Positive:** Schema changes are versioned and reversible. Migrations can be applied to any environment idempotently. `alembic downgrade` supports rollback.
- **Negative:** `env.py` requires non-trivial async setup that the default template doesn't provide. Must be configured carefully once, then left alone.
- **Action required:** Add `alembic upgrade head` to the project `Makefile` or startup sequence for local dev and CI.

---

## ADR-009: Explicit Eager Loading — get() vs get_with_sources()

**Status:** Accepted
**Date:** 2026-04-05

### Context

In async SQLAlchemy, lazy loading of relationships raises `MissingGreenlet` — the ORM cannot issue a new DB query from a non-async context when a relationship attribute is accessed. This means relationships must be explicitly loaded at query time using `selectinload` or `joinedload`.

The `Vehicle` domain model has a `sources: list[Source] | None` field. `None` means "not loaded", `list` means "loaded (may be empty)".

### Decision

Two distinct methods per repository:

- `get(id)` — plain `SELECT` with no relationship loading. Returns `Vehicle` with `sources=None`. Use when sources are not needed (list views, simple lookups).
- `get_with_sources(id)` — `SELECT` with `selectinload(VehicleTable.sources)`. Returns `Vehicle` with `sources: list[Source]`. Use when sources must be displayed or processed.

All SQLAlchemy relationships are declared with `lazy="noload"` on the table models to prevent any accidental auto-loading. Eager loading only happens when explicitly requested via `selectinload()` in a query.

Callers that receive `sources=None` and then try to access sources know they must call `get_with_sources` instead.

### Alternatives considered

- **Always eager load:** Every `get()` loads sources. Simpler API but wasteful — most list/lookup operations don't need sources, and the JOIN adds cost proportional to the number of sources.
- **`lazy="select"` (default):** SQLAlchemy issues a second query automatically when the attribute is accessed. Works in sync context; raises `MissingGreenlet` in async.
- **`None` vs `[]` to signal "not loaded":** `[]` is ambiguous — does it mean "no sources exist" or "sources not fetched"? `None` is unambiguous. Callers can distinguish between "vehicle has no sources" (`sources=[]`) and "sources not fetched" (`sources=None`).

### Consequences

- **Positive:** No `MissingGreenlet` errors. Explicit loading is visible at the call site. Performance: list endpoints don't pay the cost of loading relationships.
- **Negative:** Callers must know which method to use. Two methods per entity pair (e.g., future phases may add more relationships, each requiring a new method variant).

---

## ADR-010: SourceRepository Owns the Vehicle-Source Many-to-Many Relationship

**Status:** Accepted
**Date:** 2026-04-05

### Context

The `vehicle_sources` join table represents a many-to-many relationship. Both `VehicleRepository` and `SourceRepository` could claim ownership of the join table. Ownership determines which repository has `link` and `unlink` methods.

Additionally, a third `VehicleSourceRepository` could be introduced as a dedicated owner of the join table.

### Decision

`SourceRepository` owns the relationship. It has `link_vehicle(source_id, vehicle_id)`, `unlink_vehicle(source_id, vehicle_id)`, and `get_vehicles_for_source(source_id)` methods.

`VehicleRepository` reads the relationship via `selectinload` in `get_with_sources()` but never writes to the join table.

No separate `VehicleSourceRepository` is created.

### Alternatives considered

- **VehicleRepository owns it:** Semantic case: "add a source to a vehicle." However, this creates an asymmetry — you can't query "what vehicles reference this source" without going through VehicleRepository, which would then need to know about SourceTable.
- **Separate VehicleSourceRepository:** Cleanest separation but unnecessary indirection for two entities. Would be worth it if the join table had its own attributes (e.g., `linked_at`, `priority`). It currently has none.
- **Both repositories share it:** Leads to duplication and potential conflicts on the join table.

### Consequences

- **Positive:** Ownership is clear and localized. `SourceService` handles all relationship mutations. `VehicleService` is read-only with respect to the relationship.
- **Negative:** Slightly counter-intuitive that linking a source to a vehicle is done via `SourceService.link_vehicle(source_id, vehicle_id)` rather than `VehicleService`. Mitigated by clear method naming and documentation.
- **If the join table gains attributes later:** Promote to a mapped class and introduce `VehicleSourceRepository` at that time.

---

## ADR-011: Domain Exceptions for Cross-Boundary Error Translation

**Status:** Accepted
**Date:** 2026-04-05

### Context

SQLAlchemy raises infrastructure exceptions (`IntegrityError`, `NoResultFound`) when DB operations fail. If these leak into the route layer, FastAPI would return 500s for what are actually 409 Conflict or 404 Not Found situations. Additionally, infrastructure exception types should never be visible to the application layer.

### Decision

A `domain/exceptions.py` module defines domain-level exceptions:

- `VehicleAlreadyExistsError` — `(manufacturer, model_name, year)` collision
- `VehicleNotFoundError` — lookup by ID returned nothing
- `SourceAlreadyExistsError` — duplicate URL
- `SourceNotFoundError` — lookup by ID returned nothing
- `VehicleSourceLinkError` — link/unlink operation in invalid state

Repository methods catch `sqlalchemy.exc.IntegrityError` and re-raise as the appropriate domain exception. Services catch `NoResultFound` (or check for `None` return) and raise `*NotFoundError`.

FastAPI exception handlers (or route-level `try/except`) map domain exceptions to HTTP responses: `*AlreadyExistsError` → 409, `*NotFoundError` → 404, `VehicleSourceLinkError` → 409.

### Alternatives considered

- **Let SQLAlchemy exceptions propagate:** FastAPI would catch them as unhandled exceptions and return 500. Incorrect semantics, leaks ORM details into HTTP responses.
- **HTTP exceptions in services:** Services raise `fastapi.HTTPException` directly. Couples business logic to HTTP. Services become untestable without HTTP context.

### Consequences

- **Positive:** Clean separation — infrastructure errors stay in infrastructure, business errors stay in domain, HTTP errors stay in routes. Services are testable without an HTTP context.
- **Negative:** Requires a `try/except` at every repository mutation that could violate a constraint. Mechanical but consistent.

---

## ADR-012: Two-Level Test Strategy (Unit + Integration; E2E Deferred)

**Status:** Accepted
**Date:** 2026-04-05

### Context

Testing requires both confidence in business logic (services) and confidence in the full HTTP stack (routes). A real DB adds setup complexity (provisioning, migrations, teardown). The clean architecture (ADR-001) and repository protocols (ADR-004) enable DB-free testing at both levels.

### Decision

**Level 1 — Unit tests:** Instantiate services directly with in-memory repository fakes. No FastAPI, no DB, no HTTP. Tests run in milliseconds. Cover all business logic branches.

```python
async def test_create_duplicate_vehicle():
    repo = InMemoryVehicleRepository()
    service = VehicleService(repo)
    await service.create(input)
    with pytest.raises(VehicleAlreadyExistsError):
        await service.create(input)
```

**Level 2 — Integration tests:** Use `httpx.AsyncClient` with `app.dependency_overrides` to replace Postgres repos with in-memory fakes. Tests the full HTTP route → service → repo chain. No DB required.

```python
app.dependency_overrides[get_vehicle_repo] = lambda: InMemoryVehicleRepository()
```

**Level 3 — E2E (deferred):** Real DB, Alembic migrations run before suite, no dependency overrides. Validates actual SQL, constraints, and transactions. Added when CI test DB is provisioned.

In-memory repositories live in `tests/fakes/` and are considered test infrastructure, not production code.

### Consequences

- **Positive:** Unit tests are zero-infrastructure — run anywhere, anytime. Integration tests validate HTTP behavior without DB. E2E can be added incrementally.
- **Negative:** In-memory fakes must accurately mirror Postgres behavior (uniqueness, not-found semantics). If fakes drift from real behavior, integration tests pass but E2E fails.
- **Mitigation:** In-memory fakes enforce the same uniqueness rules as the DB (raise `VehicleAlreadyExistsError` on duplicate). Consistency is verified when E2E tests are added.

---

## ADR-013: Enum Extensibility Without catch-all `other`

**Status:** Accepted
**Date:** 2026-04-05

### Context

Domain enums (`VehicleClass`, `BodyType`, `Transmission`, `FuelType`, `SourceType`) need to cover the known value set without preventing future extension. A common pattern is to include an `other` value as a catch-all for unknown cases.

### Decision

No `other` value in any enum. Enums are extended by adding new members in future migrations. Existing rows are not affected by enum additions. If an analyst encounters a vehicle that doesn't fit current values, they must wait for the enum to be extended — or use the `notes: str | None` field on `Vehicle` to capture freeform context.

### Alternatives considered

- **`other` as catch-all:** Allows immediate accommodation of edge cases but creates an information sink — stored `other` rows carry no semantic meaning. Queries like "show me all electric vehicles" become unreliable if some electric vehicles were stored as `other` before `electric` was added.
- **Free text instead of enum:** Full flexibility but no queryability or validation.

### Consequences

- **Positive:** All stored values carry precise meaning. Queries on enum fields are reliable. No ambiguous `other` rows to clean up later.
- **Negative:** New vehicle types require a schema migration to add the enum value. In PostgreSQL, adding an enum value is a DDL operation (`ALTER TYPE ... ADD VALUE`) — it is non-transactional but fast and does not lock the table.
- **`notes: str | None`** on `Vehicle` serves as the escape hatch for capturing freeform context when no enum value fits.

---

*ADRs.md — Phase 1: Business Domain Integration*
*Created: 2026-04-05*
