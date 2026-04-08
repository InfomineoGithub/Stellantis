# Project State

## Project Reference

See: .paul/PROJECT.md (updated 2026-04-05)

**Core value:** Save automotive acquisition teams time and budget by automatically extracting and classifying car parameters from web, video, and document sources — replacing manual research.
**Current focus:** Phase 1 — Business Domain Integration (complete — ready for next phase planning)

## Current Position

Milestone: v0.1 — Business Domain Integration
Phase: 1 — Business Domain Integration — **COMPLETE**
Plan: .paul/phases/01-business-domain-integration/PLAN.md
Summary: .paul/phases/01-business-domain-integration/PLAN-SUMMARY.md
Status: Loop closed — ready for next phase
Last activity: 2026-04-05 — Phase 1 fully built and unified, 20/20 tests passing

Progress:
- Milestone: [██████████] 100% (Phase 1 of 1 complete)
- Phase 1:   [██████████] 100% — Complete

## Loop Position

Current loop state:
```
PLAN ──▶ APPLY ──▶ UNIFY
  ✓        ✓        ✓     [Loop complete — ready for next PLAN]
```

## Accumulated Context

### Decisions

| Decision | Phase | Impact |
|----------|-------|--------|
| Build on DeerFlow (LangGraph + FastAPI + Next.js) | Init | All agent and API work uses existing infrastructure |
| PostgreSQL for persistence | Init | Need to add DB layer — not in current DeerFlow base |
| Better Auth + JWT cookies, no RBAC | Init | Auth already in codebase; no role work needed |
| Parameters are global (160 for all cars) | Init | No per-car parameter customization for now |
| Deploy on GCP | Init | Cloud target for production |
| Clean architecture with strict layer separation | Phase 1 | Domain/infra decoupled; see ADR-001 |
| DeclarativeBase over SQLModel | Phase 1 | Explicit domain↔infra translation; see ADR-002 |
| Pure Pydantic BaseModel for domain | Phase 1 | Zero ORM imports in domain layer; see ADR-003 |
| Repository Protocol (not ABC) | Phase 1 | Structural subtyping, easier fakes; see ADR-004 |
| FastAPI dependency_overrides for DI | Phase 1 | Per-request instantiation, testable; see ADR-005 |
| Single session + session.begin() auto-commit | Phase 1 | Atomicity across repos, no manual commit; see ADR-006 |
| UUID primary keys | Phase 1 | Non-enumerable, generated before insert; see ADR-007 |
| Alembic with async env.py | Phase 1 | Versioned migrations with asyncpg; see ADR-008 |
| get() vs get_with_sources() explicit loading | Phase 1 | No MissingGreenlet, intentional eager load; see ADR-009 |
| SourceRepository owns vehicle-source join | Phase 1 | Single owner of vehicle_sources table; see ADR-010 |
| Domain exceptions layer | Phase 1 | IntegrityError never leaks past service; see ADR-011 |
| Two-level test strategy (unit + integration) | Phase 1 | In-memory fakes, no DB required for CI; see ADR-012 |
| No other catch-all in enums | Phase 1 | All values carry precise meaning; see ADR-013 |

### Deferred Issues

| Issue | Origin | Effort | Revisit |
|-------|--------|--------|---------|
| RAG/document knowledge base tool ("Rack 4") | Init | M | When document source integration is planned |
| Internal grounding framework | Init | L | When budget/timeline allows |
| Dynamic add/remove parameters | Init | S | When business confirms requirement |
| Agent-assisted web navigation | Init | L | If budget/timeline allows after core delivery |
| E2E tests with real DB | Phase 1 | S | When CI test DB is provisioned |
| VehicleSourceRepository (if join table gains attributes) | Phase 1 | S | If vehicle_sources needs its own columns |

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-04-05
Stopped at: Phase 1 complete — UNIFY done, loop closed
Next action: Run /paul:plan to plan the next phase (Parameters domain, Run orchestration, or Agent integration — TBD by business priority)
Resume file: .paul/phases/01-business-domain-integration/PLAN-SUMMARY.md

---
*STATE.md — Updated after every significant action*
