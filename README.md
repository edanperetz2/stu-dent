# Stu-Dent

Dental student appointment management system. Coordinates real patients, dental
students, attending (mentoring) dentists, rooms, and equipment — replacing the
WhatsApp/spreadsheet workflow currently used. See `docs/proposal.md` for the
full project proposal and `CLAUDE.md` for the phase roadmap and conventions.

Localhost-first, fully Dockerized, zero paid services.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, pytest
- DB: PostgreSQL 16
- Frontend: React + Vite + TypeScript
- Infra: Docker Compose (`api`, `db`, `frontend`, `mailhog`)

## Prerequisites

- Docker Desktop (with Docker Compose v2), running before any command below.
- No local Python/Node installation is required — everything runs in containers.

## First run (Windows / PowerShell)

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Then open:

- API: http://localhost:8000/health
- API docs (Swagger): http://localhost:8000/docs
- Frontend: http://localhost:5173
- MailHog web UI: http://localhost:8025

Stop the stack with `Ctrl+C`, then `docker compose down` (add `-v` to also drop
the Postgres volume and start from a clean database).

## Running database migrations

Migrations run automatically on `api` container start. To run them manually
(e.g. after pulling new migrations without a full restart):

```powershell
docker compose exec api alembic upgrade head
```

To create a new migration after changing a SQLAlchemy model:

```powershell
docker compose exec api alembic revision --autogenerate -m "describe the change"
```

## Running tests

```powershell
docker compose exec api pytest -v
```

## Linting

```powershell
docker compose exec api ruff check .
docker compose exec api black --check .
docker compose exec frontend npm run lint
```

## Known Phase 1 limitations

- `POST /auth/register` accepts a `role` field with no admin gating — anyone
  can self-register as `student`, `attending`, or `admin`. This is an accepted
  simplification for a course project and is not production-safe.
- Patient login credentials are provisioned directly by the owning student
  (no self-service signup or email invite flow yet).
