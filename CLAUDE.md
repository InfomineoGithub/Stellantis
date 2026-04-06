# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeerFlow 2.0 is a LangGraph-based AI super agent platform with sandbox code execution, persistent memory, subagent delegation, and extensible tools/skills. It's a full-stack application: a Python backend (LangGraph + FastAPI) and a Next.js frontend, unified behind an Nginx reverse proxy.

**Ports**:
- `2026` — Nginx (unified entry point, use this in the browser)
- `2024` — LangGraph Server (agent runtime)
- `8001` — Gateway API (REST: models, MCP, skills, memory, uploads)
- `3000` — Next.js Frontend

## Commands

**From the project root** (manages all services together):
```bash
make check      # Verify system requirements (Node 22+, pnpm, uv, nginx)
make config     # Generate local config files from examples
make install    # Install all dependencies (frontend + backend)
make dev        # Start all services with hot-reload → http://localhost:2026
make stop       # Stop all services
make up         # Docker production build and start
make down       # Stop Docker containers
make docker-init    # Pull sandbox Docker image
make docker-start   # Start Docker-based dev environment
```

**Backend only** (from `backend/`):
```bash
make install    # Install Python dependencies via uv
make dev        # LangGraph server (port 2024)
make gateway    # Gateway API (port 8001)
make test       # Run all backend tests
make lint       # Lint with ruff
make format     # Format with ruff

# Run a specific test file
PYTHONPATH=. uv run pytest tests/test_<feature>.py -v
```

**Frontend only** (from `frontend/`):
```bash
pnpm dev        # Dev server with Turbopack (port 3000)
pnpm build      # Production build
pnpm check      # Lint + type check (run before committing)
pnpm lint:fix   # ESLint with auto-fix
```

## Architecture

```
Browser → http://localhost:2026
    ↓
[Nginx :2026]
  ├─ /api/langgraph/* → LangGraph Server :2024 (AI orchestration)
  ├─ /api/*           → Gateway API :8001 (FastAPI REST)
  └─ /               → Frontend :3000 (Next.js)
```

### Backend split: Harness vs App

The backend has a strict dependency boundary:

- **Harness** (`backend/packages/harness/deerflow/`): Publishable package (`deerflow-harness`). Contains everything for agent execution — LangGraph agent, 11 middleware chain, sandbox, tools, MCP, skills, models, memory. Import prefix: `deerflow.*`
- **App** (`backend/app/`): Unpublished application layer. FastAPI Gateway API and IM channel integrations (Feishu, Slack, Telegram). Import prefix: `app.*`

App may import deerflow; deerflow must never import app. This is enforced by `backend/tests/test_harness_boundary.py` which runs in CI.

### Configuration files (project root)

- `config.yaml` — Main config (copy from `config.example.yaml`). Controls LLMs, tools, sandbox, memory, channels. Values starting with `$` are resolved as env vars.
- `extensions_config.json` — MCP servers and skills on/off state. Updated at runtime via Gateway API.
- `.env` — API keys

## Development Guidelines

### TDD is mandatory

Every new feature or bug fix must be accompanied by tests in `backend/tests/`. No exceptions. Run `make test` before and after changes.

### Documentation update policy

After every code change, update:
- `README.md` for user-facing changes
- `CLAUDE.md` (this file or the relevant sub-directory one) for development/architecture changes

### Sub-directory CLAUDE.md files

Detailed guidance lives closer to the code:
- `backend/CLAUDE.md` — Full backend architecture: agent system, middleware chain, sandbox, MCP, memory, subagents, config schema, all API routes
- `frontend/CLAUDE.md` — Frontend architecture: data flow, component layout, code style, environment setup
