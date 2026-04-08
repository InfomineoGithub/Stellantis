# Stellantis Automotive Intelligence

## What This Is

A platform built on DeerFlow (LangGraph + FastAPI + Next.js) that automates automotive parameter acquisition. Users define a car and its sources; an AI agent searches, scrapes, and crawls those sources to extract up to 160 predefined parameters per car. Each parameter is identified, classified (high/medium/low), and stored in a database. The platform supports single-car and multi-car batch runs, and generates validation reports for users to review and approve findings.

## Core Value

Save automotive acquisition teams time and budget by automatically extracting and classifying car parameters from web, video, and document sources — replacing manual research.

## Current State

| Attribute | Value |
|-----------|-------|
| Type | Application |
| Version | 0.1.0 |
| Status | In Progress |
| Last Updated | 2026-04-05 |

## Requirements

### Core Features

- Define a car and its configuration (make, model, specs)
- Define and manage sources per car — a source is a domain (crawled) or a specific URL (fetched/scraped), linked to one or multiple cars
- Run the agent — single car or batch of cars — which searches, scrapes, and extracts parameters from sources
- Review and validate findings — users can validate or disqualify parameter results per run
- Manage the 160 global parameters and their classification rules (high/medium/low)
- Chat with a helper agent to ask questions about specific parameters or findings

### Validated (Shipped)

- ✓ Define a car (vehicle) with configuration — Phase 1
- ✓ Define and manage sources per car — Phase 1
- ✓ PostgreSQL persistence layer (Vehicle, Source, vehicle_sources) — Phase 1
- ✓ Clean architecture foundation (domain / repository / service / router) — Phase 1
- ✓ REST API: CRUD for vehicles and sources, link/unlink vehicles to sources — Phase 1
- ✓ React Query frontend data layer (types, keys, api, hooks) for vehicles and sources — Phase 1

### Active (In Progress)
None.

### Planned (Next)
- To be defined during /paul:plan

### Out of Scope

- Adding/removing parameters dynamically — business need not yet confirmed, deferred
- Agent-assisted web navigation for users — deferred (budget/timeline dependent)
- Internal grounding framework (company-developed) — deferred
- Role-based access control (RBAC) — not required

## Target Users

**Primary:** Automotive acquisition analysts / engineers
- Responsible for collecting and validating car parameters
- Currently do this manually by searching the web, videos, and documents
- Need to process many cars with up to 160 parameters each

## Context

**Business Context:**
The current parameter acquisition process is manual and time-consuming. Each car requires searching the internet for up to 160 parameters. This platform automates that process to speed up acquisition timelines and reduce research cost for Stellantis.

**Technical Context:**
Built on top of DeerFlow 2.0 — a LangGraph-based AI super agent platform with sandbox code execution, persistent memory, subagent delegation, and extensible tools/skills. The flow is being modified to accommodate automotive acquisition business needs rather than deployed as-is.

## Constraints

### Technical Constraints

- Must use DeerFlow stack: LangGraph + FastAPI backend, Next.js frontend, Nginx proxy
- PostgreSQL required for persistent storage (cars, sources, parameters, runs, findings)
- Better Auth with JWT tokens stored in client-side cookies
- No RBAC — single user tier
- Source retrieval strategy determined by type: domain → crawl, URL → fetch/scrape
- External paid APIs likely required (specific APIs TBD)
- RAG/document knowledge base to be integrated (tool TBD — referenced as "Rack 4")

### Business Constraints

- Timeline: Not yet assigned
- Budget: Not yet assigned
- Parameters are global (same 160 for all cars); dynamic add/remove deferred until business confirms need

### Compliance Constraints

- To be defined during /paul:plan

## Key Decisions

| Decision | Rationale | Date | Status |
|----------|-----------|------|--------|
| Build on DeerFlow instead of greenfield | Leverage existing LangGraph agent infrastructure | 2026-04-05 | Active |
| PostgreSQL for persistence | Structured data with relational needs (cars, runs, findings) | 2026-04-05 | Active |
| No RBAC | Business requirement — single user tier for now | 2026-04-05 | Active |
| Better Auth + JWT in cookies | Auth approach already in codebase | 2026-04-05 | Active |
| Deploy on GCP | Cloud hosting target | 2026-04-05 | Active |
| Clean architecture (domain/infra/service/router) | Domain models stay DB-agnostic; infra is swappable | 2026-04-05 | Active |
| DeclarativeBase over SQLModel | Enforces strict domain↔infra boundary | 2026-04-05 | Active |
| Repository Protocol (not ABC) | Structural subtyping, easier in-memory fakes for tests | 2026-04-05 | Active |
| FastAPI dependency_overrides for DI | Per-request instantiation; test isolation without mocks | 2026-04-05 | Active |
| Domain exceptions layer | IntegrityError never leaks past service boundary | 2026-04-05 | Active |

## Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| End-to-end run completion (single car) | 100% | - | Not started |
| End-to-end run completion (multi-car batch) | 100% | - | Not started |
| Parameter extraction rate per run | Maximize (target TBD) | - | Not started |
| User can define car + sources + validate | Working flow | - | Not started |

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Agent Orchestration | LangGraph | Core agent runtime |
| Backend API | FastAPI | Gateway API (port 8001) |
| Frontend | Next.js | User interface (port 3000) |
| Database | PostgreSQL | Cars, sources, parameters, runs, findings |
| Auth | Better Auth | JWT in cookies, no RBAC |
| Proxy | Nginx | Unified entry point (port 2026) |
| Document Knowledge Base | TBD ("Rack 4") | RAG for document sources |
| Cloud | GCP | Production hosting |
| Grounding Framework | Internal (company) | Deferred — evaluate if time/budget allows |

## Links

| Resource | URL |
|----------|-----|
| Repository | C:/computer/programming/infomineo/Stellantis |

---
*PROJECT.md — Updated when requirements or context change*
*Last updated: 2026-04-05 after Phase 1*
