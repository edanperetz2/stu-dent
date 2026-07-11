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
- Infra: Docker Compose (`api`, `db`, `frontend`, `mailhog`, `worker`, `ollama`)

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

## Local AI (Ollama)

The scheduling-interpretation and report/Q&A assistant features call a
local Ollama model. After the first `docker compose up`, pull the model
once (it isn't baked into the `ollama/ollama` image):

```powershell
docker compose exec ollama ollama pull llama3.2
```

Both features degrade gracefully (a plain warning / raw-data fallback,
never an error) if Ollama is unreachable or the model isn't pulled yet.

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

## Seeding demo data

Populates the database with realistic sample data (students, attendings,
patients across both onboarding paths, appointments in most states, forum
posts, direct messages, reports, etc.) so a demo doesn't start from an
empty app. Safe to re-run — idempotent, no-ops if already seeded.

```powershell
docker compose exec api python -m app.seed_demo
```

Prints every seeded account's login at the end (one shared password for
all of them).

## Linting

```powershell
docker compose exec api ruff check .
docker compose exec api black --check .
docker compose exec frontend npm run lint
```

## Deploying to the course VM

This project targets a plain Linux VM (not a managed cloud platform) —
Postgres, Ollama, and everything else just run as Docker containers on the
VM itself, the same shape as local `docker compose up`, just hardened for
production via `docker-compose.prod.yml`. **These steps haven't been run
against a real VM yet** (written before one was available) — the most
likely adjustment needed is the exact address the VM is reachable at;
everything else should work as described.

**First-time setup** (once the VM exists and you can SSH into it):

```bash
ssh <your-user>@<vm-ip>
curl -fsSL https://raw.githubusercontent.com/edanperetz2/stu-dent/master/deploy/bootstrap-vm.sh | bash
git clone https://github.com/edanperetz2/stu-dent.git
cd stu-dent
cp .env.example .env
```

Edit `.env`:
- `VITE_API_URL` → this VM's real address, e.g. `http://<vm-ip>:8000`
- `FRONTEND_ORIGINS` → include this VM's frontend URL too, e.g.
  `http://localhost:5173,http://<vm-ip>` — **this one is easy to miss**;
  forgetting it produces a real, confusing "login failed" with no obvious
  error in the UI (the browser silently blocks the cross-origin request).
- `JWT_SECRET_KEY` → generate a real random value, don't keep the example.

Then bring up the production stack:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec ollama ollama pull llama3.2  # optional, one-time
```

Visit `http://<vm-ip>` for the frontend, `http://<vm-ip>:8025` for MailHog
(useful for demoing "the app really sent an email" live).

**Redeploying after a code change**: either SSH in again and re-run
`git pull && docker compose -f docker-compose.prod.yml up -d --build`, or
set up push-button redeploys via `.github/workflows/deploy.yml`
(`workflow_dispatch`-only, never runs automatically):

1. Generate a dedicated SSH keypair for CI (don't reuse your personal
   one) and add the public half to the VM's `~/.ssh/authorized_keys`.
2. Add three GitHub repo secrets: `VM_HOST`, `VM_USER`, `VM_SSH_KEY`
   (the private half of the deploy keypair).
3. Go to Actions → "Deploy to VM" → "Run workflow".

## Known Phase 1 limitations

- `POST /auth/register` accepts a `role` field with no admin gating — anyone
  can self-register as `student`, `attending`, or `admin`. This is an accepted
  simplification for a course project and is not production-safe. A real
  identity-verification + admin-approval gate for student/attending signups
  is planned but not yet designed — see `CLAUDE.md`'s Backlog section.
- Patients have two onboarding paths: a student can create one directly
  with credentials (`POST /patients`, auto-confirmed immediately), or a
  patient can self-register via `/auth/register` picking their student
  from the public `GET /students` directory — this leaves the connection
  pending until the chosen student calls `POST /patients/{id}/confirm`.
  An unconfirmed patient can log in and view their own profile but is
  blocked from booking appointments or messaging until confirmed.
