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

---

## ADR-014: JWT Bearer Tokens as the Identity Transport Between Frontend and Backend Services

**Status:** Accepted
**Date:** 2026-04-06

### Context

DeerFlow 2.0 runs as three independent services behind an Nginx reverse proxy: the Next.js frontend (port 3000), the Gateway API (FastAPI, port 8001), and the LangGraph agent runtime (port 2024). Users authenticate exclusively via Google OAuth — email/password is disabled. There is no RBAC; any authenticated user can access all endpoints.

The question is how the frontend proves the caller's identity to the backend services after authentication. Two viable approaches exist:

1. **Cookie-forwarding (session proxy):** The browser sends the Better Auth session cookie to the backend. The backend makes a network call to Next.js to exchange the cookie for identity claims on every request.
2. **JWT bearer tokens:** Better Auth issues a short-lived signed JWT. The frontend caches it and attaches it as `Authorization: Bearer <token>` on every request. The backend validates the signature locally using a shared secret.

### Decision

Use **short-lived JWT bearer tokens** (HS256, signed by `BETTER_AUTH_SECRET`) as the identity transport.

Better Auth's `jwt()` plugin exposes `/api/auth/token`. The frontend's `fetchWithAuth` calls this endpoint when a valid session cookie exists, caches the returned JWT for 14 minutes (token TTL is 15 minutes), and attaches it as an `Authorization: Bearer <token>` header on all requests to the Gateway API and LangGraph server.

Both backend services validate the token using the shared `verify_jwt()` function from the `stellantis-auth` package:

```
Strategy: Try HS256 with BETTER_AUTH_SECRET (fast, no network) →
          Fall back to JWKS at /api/auth/jwks (asymmetric, for future key rotation)
```

The Gateway injects the validated payload via `Depends(get_current_user)`. LangGraph registers `@auth.authenticate` in `langgraph.json`. Both share the same `verify_jwt()` implementation.

A `BYPASS_AUTH=true` environment variable skips validation in local development. This flag is checked at runtime in both services.

### Alternatives considered

- **Cookie-forwarding (session proxy):** The browser sends the session cookie; backends call Next.js `/api/auth/token` (or a custom introspection endpoint) on every request to resolve identity. Rejected because: it creates a hard runtime dependency from every backend service to the Next.js server on every authenticated request; LangGraph's `@auth.authenticate` hook has no standard HTTP client; and it prevents horizontal scaling of backends without sticky sessions or a shared Next.js session store.

- **Asymmetric JWT (RS256 / EdDSA via JWKS only):** Eliminates the shared-secret coordination problem — backends fetch the public key from the JWKS endpoint without knowing the private key. Not chosen as the primary strategy because it introduces a network round-trip for key discovery and requires asymmetric key infrastructure. The JWKS fallback is already implemented in `verifier.py` and can be promoted to the primary strategy without changing callers.

### Consequences

- **Positive:** Validation is stateless and network-free (HS256 path). Both backend services use the same `verify_jwt()` call — adding a new service requires only sharing `BETTER_AUTH_SECRET`. Token caching in the frontend (14-min TTL, 15-min token) keeps round-trips to `/api/auth/token` minimal.
- **Negative:** `BETTER_AUTH_SECRET` must be consistent across all services — rotating it invalidates all live tokens immediately. No revocation before expiry: if a user's Google account is suspended, existing JWTs remain valid for up to 15 minutes (acceptable without RBAC).
- **Accepted trade-off:** The 15-minute expiry window on non-revocable tokens is acceptable at this stage. Rotation risk is mitigated by deploying all services in a single coordinated step. If revocation or finer-grained control is needed in a later phase, the JWKS path supports key rotation without changing the validation interface.
- **Key files:**
  - Token fetch and 14-min cache: `frontend/src/core/api/auth-fetch.ts`
  - LangGraph client header injection: `frontend/src/core/api/api-client.ts`
  - Better Auth config (`jwt()` plugin): `frontend/src/server/better-auth/config.ts`
  - Shared JWT verifier (HS256 + JWKS): `backend/packages/auth/jwt_auth/verifier.py`
  - Gateway dependency: `backend/app/gateway/dependencies.py`
  - LangGraph auth hook: `backend/src/auth.py`

---

## ADR-015: Mtime-Based Config Cache Invalidation Without a File Watcher

**Status:** Accepted
**Date:** 2026-04-14

### Context

`get_app_config()` returns a cached singleton so the config file is not re-parsed on every API request. During development the config file changes frequently (model keys, tool toggles, sandbox settings) and the previous implementation never reloaded — the server had to be restarted to pick up changes.

Two approaches exist for detecting file changes:

1. **File-watcher daemon** (watchfiles, watchdog): A background thread/process watches the filesystem for inotify/FSEvents/ReadDirectoryChangesW events and signals the application to reload.
2. **Mtime polling on access**: Each call to `get_app_config()` reads the file's `st_mtime_ns` and compares it to the cached value. If different, the config is reloaded before returning.

### Decision

Use **mtime polling on access** (`Path.stat().st_mtime_ns` comparison on every `get_app_config()` call). No file-watcher dependency is added.

The cache stores three globals: `_app_config`, `_app_config_path`, and `_app_config_mtime_ns`. All three are cleared together by `reset_app_config()` and updated atomically on reload. If the path or mtime has changed since the last read, the config is reloaded transparently.

### Alternatives considered

- **File-watcher daemon (watchfiles):** Already in the dependency tree (LangGraph uses it for hot-reload). Would push reload to a background thread rather than the hot path of each request. Adds complexity: thread lifecycle, synchronisation, and platform-specific behaviour (FSEvents vs inotify vs ReadDirectoryChangesW). On Windows the watcher holds a directory handle that prevents `TemporaryDirectory` cleanup in tests. Rejected: the polling cost is negligible for a config that changes only during development.

- **Explicit `reload_app_config()` call required:** Force callers to call `reload_app_config()` whenever they know the file changed. Simpler internally but requires coordination — the Gateway API would need to reload on every mutating request and the LangGraph server would need its own reload path. Rejected: error-prone and inconsistent.

### Consequences

- **Positive:** Config changes are picked up automatically by the next API call — no restart required. No new dependency. The cache is always coherent: path, mtime, and the config object are updated together.
- **Negative:** Every `get_app_config()` call does one `stat()` syscall. Acceptable — `stat()` is a fast VFS call and config is read only on the critical path for agent initialisation, not on every token produced.
- **Key files:** `backend/packages/harness/deerflow/config/app_config.py` (`get_app_config`, `reload_app_config`, `reset_app_config`, `_read_config_cache_metadata`)

---

## ADR-016: Built-in Adapter Layer to Eliminate Base64 and Full-Content Round-Trips

**Status:** Accepted
**Date:** 2026-04-27

### Context

Two categories of MCP tools force the agent to handle raw binary data inline, bloating the context window on every file-related operation:

1. **RAGFlow upload/download** — `upload_with_metadata` and `download_attachment` exchange file content as base64-encoded strings passed directly as tool call arguments and results. A 100 KB PDF adds ~133 KB of base64 noise per operation; multi-page documents reach megabyte scale. The agent must construct or parse the full base64 string even though it has no semantic use for the binary content.

2. **Cloudflare `browser_render_markdown`** — returns the full rendered Markdown of a fetched page as a tool result. When the agent needs to save content to disk it receives the full text in the result, then re-passes the full text as an argument to a write call. Content doubles in context on every web-fetch-to-file flow.

Both patterns burn tokens on encoding overhead, degrade model attention, and increase API cost multiplicatively when multiple file operations occur in a single task.

### Decision

Introduce a **built-in adapter layer** (`deerflow/tools/adapters/`) that wraps the raw MCP tools. Adapter tools expose a path-based interface to the model — the model works with file paths only. All base64 encoding/decoding, HTTP fetching, and file I/O happen server-side, transparent to the model.

Three adapter tools are provided:
- `ragflow_upload` — accepts a file path, reads and encodes the file internally, calls `upload_with_metadata`.
- `ragflow_download` — accepts doc IDs and an output directory, calls `download_attachment`, decodes base64, and writes files to disk. Returns saved paths only.
- `fetch_url` — accepts a URL and output directory. Webpages: calls `browser_render_markdown` and writes the Markdown to a file. Binary files (PDF, DOCX, XLSX, PPTX): fetches via httpx and writes bytes directly.

### Alternatives considered

- **Prompt-based instructions to avoid base64 in context:** Instruct the model to avoid reading base64 output. Unreliable — the tool result appears in context regardless.
- **MCP server-side changes:** Modify RAGFlow's MCP tool to accept file paths. Requires upstream changes outside this project's control.
- **Stripping tool results from context:** Post-process messages to remove large tool results. Breaks agent reasoning continuity; not a general solution.

### Consequences

- **Positive:** Model never sees base64 or full page content. Token cost per file operation drops proportionally to file size. Works transparently — adapter tools are loaded alongside regular MCP tools.
- **Negative:** The adapter layer adds a mapping between logical tool names and actual MCP tool names. If the MCP tool name changes, `tool_mappings` in `extensions_config.json` must be updated.
- **Constraint:** Adapters must be enabled explicitly; raw MCP tools remain available unless `hide_wrapped_tools: true` is set.

---

## ADR-017: Adapter Internal Architecture — `_do_*` / `make_*_tool` Split

**Status:** Accepted
**Date:** 2026-04-27

### Context

Each adapter tool needs two distinct behaviors: (a) pure file/network I/O logic that is unit-testable without LangGraph context, and (b) a LangChain `BaseTool`-compatible wrapper that resolves virtual paths from the LangGraph runtime before delegating to the I/O logic.

### Decision

Each adapter module is split into two layers:

**`_do_*` functions** — pure I/O implementation. Accept and return real host paths only. No runtime, no virtual path logic. Directly testable with `MagicMock` MCP tools and `tmp_path`.

```python
def _do_upload(path: str, dataset_id: str, ..., upload_mcp: BaseTool) -> str: ...
def _do_download(doc_ids: list[str], output_dir: str, ..., download_mcp: BaseTool) -> str: ...
def _do_fetch(url: str, output_dir: str, content_type: str | None, webpage_mcp: BaseTool) -> str: ...
```

**`make_*_tool` functions** — factory that returns a `BaseTool`. The inner `@tool`-decorated function:
1. Accepts `runtime: ToolRuntime` (LangGraph-injected, invisible to the model — excluded from `tool.args`).
2. Calls `get_thread_data(runtime)` to retrieve per-thread path mappings.
3. Translates virtual input paths via `replace_virtual_path(path, thread_data)`.
4. Delegates to the corresponding `_do_*` function with real paths.
5. Masks real paths in the output via `mask_local_paths_in_output(result, thread_data)`.

The MCP tool reference is closed over at construction time — each adapter tool instance wraps a specific MCP tool object looked up from the live `mcp_tools` list.

```
Adapter registry (adapters/__init__.py)
  └── load_adapter_tools(extensions_config, mcp_tools)
        ├── looks up module by adapter name
        ├── calls module.get_tools(adapter_config, mcp_tools)
        └── optionally filters mcp_tools if hide_wrapped_tools=True
```

### Alternatives considered

- **Single function combining I/O and path translation:** Simpler structure but makes unit testing require a full LangGraph `ToolRuntime` mock. The split keeps `_do_*` tests fast and dependency-free.
- **Subclassing `BaseTool` directly:** More explicit but verbose; the `@tool` decorator with `parse_docstring=True` generates the LLM-visible schema from the docstring automatically.

### Consequences

- **Positive:** `_do_*` functions are testable with zero LangGraph dependencies (37 tests, no live services). Path translation logic is centralised in the `make_*_tool` wrapper and reuses the same sandbox utilities as all other built-in tools.
- **Negative:** Two-layer split adds a small amount of indirection per adapter.
- **Extensibility:** Adding a new adapter requires only: a module with `_do_*` + `make_*_tool`, an `__init__.py` exposing `get_tools()`, and a one-line entry in `ADAPTER_REGISTRY`.

---

## ADR-018: `adapters` Section in `extensions_config.json`

**Status:** Accepted
**Date:** 2026-04-27

### Context

Adapters need per-deployment configuration: which adapters are enabled, which MCP server they wrap, whether to hide the raw wrapped tools, and the mapping from logical tool slot names to actual MCP tool names (which can vary by server version or deployment).

This configuration must be readable and writable at runtime via the same Gateway API pattern used for MCP servers and skills, and must survive `PUT /api/mcp/config` calls without being discarded.

### Decision

Add an `adapters` top-level key to `extensions_config.json` with the following schema per adapter entry:

```json
"adapters": {
  "<adapter_name>": {
    "enabled": false,
    "wraps_server": "<mcp_server_name>",
    "hide_wrapped_tools": false,
    "tool_mappings": {
      "<logical_slot>": "<actual_mcp_tool_name>"
    }
  }
}
```

Fields:
- `enabled` — whether the adapter is loaded at all. Defaults to `false` so no adapter activates without explicit opt-in.
- `wraps_server` — the MCP server name this adapter operates on. Used by `hide_wrapped_tools` filtering to identify which tools to remove from the visible set.
- `hide_wrapped_tools` — when `true`, all tools whose name starts with `<wraps_server>__` are removed from the agent's tool list once the adapter is loaded.
- `tool_mappings` — maps logical slot names (e.g. `"upload"`, `"download"`, `"webpage"`) to the actual tool name as loaded by `MultiServerMCPClient` (e.g. `"ragflow__upload_with_metadata"`). Decouples adapter logic from exact MCP naming conventions.

A new `GET /api/adapters/config` and `PUT /api/adapters/config` Gateway endpoint read/write only the `adapters` key. `PUT /api/mcp/config` is patched to preserve the `adapters` key when rewriting the file.

`extensions_config.example.json` is updated to include both adapter entries (disabled by default) as a reference for new deployments.

### Alternatives considered

- **Adapter config in `config.yaml`:** Would require restart-based config reload instead of mtime-based. Extensions config already owns MCP and skills runtime state — adapters belong there.
- **Separate `adapters_config.json` file:** Adds operational complexity with no benefit; the extensions config is already the runtime-mutable config file.
- **Hardcoded tool name mapping:** Would break when RAGFlow or Cloudflare change their MCP tool names across versions. `tool_mappings` makes the mapping explicit and operator-adjustable.

### Consequences

- **Positive:** Operators can enable/disable adapters and update tool name mappings at runtime without restarting the server. `hide_wrapped_tools` gives control over what the model sees. The UI surfaces adapter cards under each MCP server entry.
- **Negative:** Operators must verify that `tool_mappings` values match the actual tool names loaded by `MultiServerMCPClient` for their server version. A mismatch silently produces no adapter tools (adapter skips missing MCP tools gracefully).
- **Key files:** `extensions_config.json`, `extensions_config.example.json`, `deerflow/config/extensions_config.py` (`AdapterConfig`), `app/gateway/routers/adapters.py`

---

## ADR-019: Adapter Tools Are Compatible with All Three Sandbox Modes

**Status:** Accepted
**Date:** 2026-04-27

### Context

DeerFlow supports three sandbox execution modes, each with a different filesystem layout for per-thread data:

- **Local** (`LocalSandboxProvider`) — thread data lives at `backend/.deer-flow/threads/{thread_id}/user-data/{workspace,uploads,outputs}` on the host filesystem.
- **Docker / AIO** (`AioSandboxProvider`) — thread data is mounted inside a Docker container; host paths are mapped in via volume mounts.
- **Provisioner / Kubernetes** — thread data lives on a remote provisioned sandbox; paths are resolved through the provisioner URL.

In all three modes, the agent works with virtual paths (`/mnt/user-data/workspace`, `/mnt/user-data/uploads`, `/mnt/user-data/outputs`). `ThreadDataMiddleware` populates `runtime.state["thread_data"]` with the actual host paths for the current thread before any tool is called.

Adapter tools must work correctly in all three modes without mode-specific code.

### Decision

Adapter tools reuse the same virtual path resolution utilities already used by all sandbox built-in tools (`bash`, `read_file`, `write_file`):

- `get_thread_data(runtime)` — extracts `thread_data` from the LangGraph runtime state. Returns `None` if not present (e.g. in unit tests).
- `replace_virtual_path(path, thread_data)` — translates a `/mnt/user-data/...` virtual path to the real host path for the current thread. Identity function if `thread_data` is `None` or the path is already absolute and non-virtual.
- `mask_local_paths_in_output(result, thread_data)` — replaces all real host path occurrences in a result string with their virtual equivalents, so the model always sees virtual paths regardless of the underlying provider.

Because all three sandbox modes populate `thread_data` with `workspace_path`, `uploads_path`, and `outputs_path` before tool execution, adapter tools automatically work correctly in all modes. No adapter code branches on sandbox mode.

### Alternatives considered

- **Passing real paths directly to adapters:** Would couple adapter tools to the physical layout of a specific sandbox mode. The agent would need to know real paths, defeating the virtual path abstraction.
- **Adapter-specific path configuration:** A separate config field for adapter working directories. Redundant — `thread_data` already contains everything needed.

### Consequences

- **Positive:** Adapter tools are sandbox-mode agnostic. Local development, Docker dev, and Kubernetes production all work identically. No adapter code changes are needed when switching modes.
- **Negative:** Adapter tools require that `ThreadDataMiddleware` has run before they are called (i.e. they must be called within a LangGraph agent invocation). Direct invocation outside the agent context requires a `SimpleNamespace` runtime stub (as done in tests).
- **Constraint:** If `thread_data` is `None` (e.g. the middleware did not run), `replace_virtual_path` returns the path unchanged. Adapter tools will attempt to operate on the virtual path as-is, which will fail with a file-not-found error — a clear and diagnosable failure mode.

---

*ADRs.md — Phase 1: Business Domain Integration*
*Created: 2026-04-05*
