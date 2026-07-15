# Stu-Dent

Dental student appointment management system. Coordinates real patients, dental
students, attending (mentoring) dentists, rooms, and equipment — replacing the
WhatsApp/spreadsheet workflow currently used. See `docs/proposal.md` for the
full project proposal and `CLAUDE.md` for the phase roadmap and conventions.

Localhost-first, fully Dockerized, zero paid services.

## Features

- **Auth & roles**: unified login/registration for student, attending, admin,
  and patient accounts, argon2 password hashing, JWT sessions, and
  login-rate-limiting backed by the audit log.
- **Appointments**: create, approve, edit, cancel, complete, or mark a
  no-show through a table view or a full day/week/month calendar, with
  database-enforced conflict prevention across student, patient, attending,
  room, and equipment at once.
- **Waitlist**: joining happens automatically when a booking attempt hits a
  real conflict — no manual "add me to a waitlist" form. Once whatever was
  blocking it frees up, the request is booked automatically, first-come-
  first-served.
- **Notifications & email**: in-app notifications with a live unread-count
  badge, mirrored to email via MailHog for local testing, for reminders,
  cancellations, expirations, and unresolved/pending-feedback nags.
- **Forum**: a student community feed — posts, comments, and voting.
- **Messaging**: direct messages between a patient and their student,
  student/attending group chats, and a shared inbox for admin.
- **Admin management**: users, rooms, and equipment, including scheduled
  (date-limited) deactivation that auto-reactivates on its own.
- **Resources view**: an anonymized, clinic-wide room/equipment schedule so
  students and attendings can see what's free without seeing whose patient
  is using what.
- **Reports & local AI**: auto-generated weekly/monthly utilization reports,
  live ad-hoc natural-language Q&A, and a natural-language scheduling
  interpreter that pre-fills the appointment form for review — all backed by
  a local Ollama model, never trusted to make a booking decision itself.
- **Feedback**: after a completed appointment, the patient and attending (if
  one was assigned) can leave qualitative feedback for the treating student,
  with reminders until they do.

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

## Known limitations

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
