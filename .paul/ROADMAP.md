# Roadmap: Stellantis Automotive Intelligence

## Overview

Building an automotive parameter acquisition platform on top of DeerFlow. The journey goes from foundational data layer (vehicles, sources) through agent integration and parameter extraction, to reporting, validation, and the helper chat agent. Each milestone delivers a working slice of the end-to-end flow.

## Current Milestone

**v0.1 — Business Domain Integration** (v0.1.0)
Status: ✅ Complete
Phases: 1 of 1 complete

## Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 1 | Business Domain Integration | PLAN.md | ✅ Complete | 2026-04-05 |

## Phase Details

### Phase 1: Business Domain Integration

Focus: Establish the clean architecture foundation for Vehicle and Source domain entities. Includes domain models, repository protocols, PostgreSQL infrastructure (DeclarativeBase + asyncpg), Alembic migrations, services with business logic, FastAPI CRUD routes, and React Query frontend data layer.

Plans: `.paul/phases/01-business-domain-integration/PLAN.md`
Summary: `.paul/phases/01-business-domain-integration/PLAN-SUMMARY.md`
ADRs: `.paul/phases/01-business-domain-integration/ADRs.md`
Status: ✅ Complete — 2026-04-05
Tests: 20/20 passing

---
*Roadmap created: 2026-04-05*
*Last updated: 2026-04-05 — v0.1.0 milestone complete*
