# CLAUDE.md

Guidance for working on Stu-Dent. Full requirements live in `docs/proposal.md`
— treat it as the source of truth for scope; this file is conventions,
commands, and the phase roadmap.

## What this project is

Stu-Dent coordinates dental students who must give real treatments to real
patients as part of their degree, under an attending (a senior dentist who
mentors and approves procedures). Today that coordination happens over
WhatsApp and spreadsheets; this app centralizes patient records, scheduling,
shared resources (rooms/equipment), reminders, and communication.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2 (sync `Session`, `psycopg` v3
  driver — no async; not needed yet, see Phase 1 plan for rationale),
  Pydantic v2, Alembic, pytest.
- DB: PostgreSQL 16. Chosen because later phases need transactions and
  range/exclusion constraints to prevent double-booking (§4.3).
- Frontend: React + Vite + TypeScript.
- Infra: Docker Compose (`api`, `db`, `frontend`, `mailhog`), one startup
  command, `.env.example`.
- Auth: argon2 password hashing (`argon2-cffi`), JWT access tokens (`PyJWT`,
  HS256, no refresh token).

## Repo layout

```
backend/app/
  models/      SQLAlchemy ORM models
  schemas/     Pydantic request/response schemas
  core/        security (hashing/JWT), auth dependencies, rate limiting
  services/    cross-cutting helpers (e.g. audit log writer)
  api/routes/  FastAPI routers, one module per resource area
backend/alembic/versions/   one migration per schema change, no exceptions
backend/tests/              pytest, run inside the api container
frontend/src/                Vite + React + TS
docs/proposal.md            full requirements (source of truth)
```

## Conventions

- **One Alembic migration per schema change.** Never hand-edit the DB schema
  or skip a migration, even for "trivial" column additions.
- **Small, focused modules.** A route file per resource area, not one giant
  router; a model per file; no god-objects.
- **Two distinct principal types, not one role enum.** `users` (student /
  attending / admin) and `patients` (a person receiving treatment) are
  separate authenticatable entities with separate tables and separate login
  endpoints. A patient is never a 4th `role` on `users`. JWTs carry a
  `principal_type` claim (`user` | `patient`) so `core/deps.py` can dispatch
  to the right table.
- **Audit log is the rate limiter.** Login rate limiting is implemented by
  querying `audit_log` for recent failure rows for an identifier — there is
  no Redis and no in-process counter in the stack. Any new sensitive action
  should write an `audit_log` row via `services/audit.py`, not ad hoc logging.
- **Soft delete for patient records** (`deleted_at`), never a hard delete —
  preserves audit history. `users` follows the same pattern: admin-initiated
  deletion sets `deleted_at` + `is_active=False` rather than removing the row,
  since users can own patients and audit_log rows that must not be orphaned.

## Commands (run from repo root; PowerShell-compatible)

First run:
```powershell
Copy-Item .env.example .env
docker compose up --build
```

Tests:
```powershell
docker compose exec api pytest -v
```

New migration after changing a model:
```powershell
docker compose exec api alembic revision --autogenerate -m "describe the change"
docker compose exec api alembic upgrade head
```

Lint:
```powershell
docker compose exec api ruff check .
docker compose exec api black --check .
docker compose exec frontend npm run lint
```

## Known Phase 1 decisions (don't re-litigate without asking)

- `POST /auth/register` accepts a `role` field with no admin gating —
  self-service signup for any of student/attending/admin. Accepted
  simplification for a course project; called out as a limitation in the
  README, not something to "fix" unprompted. A real verification +
  admin-approval gate is planned — see Backlog below — but isn't designed
  yet, so don't half-implement it.
- Patients get real login credentials in Phase 1, provisioned by the owning
  student (no self-service signup, no email invite flow — MailHog stays
  infra-only until Phase 3's reminder/notification work).
- The attending "approves student requests for attending procedures" (§3)
  workflow is entirely Phase 2 scope (it's an appointment state machine, not
  an auth concern). Phase 1 only adds the `attending` role and one
  role-gated placeholder endpoint.
- Admin user management is done: `GET /admin/users` (list, excludes
  soft-deleted), `GET /admin/users/{id}` (detail), `PATCH /admin/users/{id}`
  (role/active status), `DELETE /admin/users/{id}` (soft delete — an admin
  cannot delete their own account). All mutations write `audit_log` rows.

## Backlog (real requirements, not yet scheduled to a phase)

- **Student/attending signup verification + admin approval.** Today,
  registering as student/attending/admin activates the account immediately
  (see the open-registration limitation above). The intended real flow:
  registering as student or attending puts the account in a pending state,
  requires an identity-verification step (mechanism not yet decided — e.g.
  document upload, university email domain check), and needs approval from
  one admin before the account can log in. This needs a schema change
  (e.g. an approval status on `users`) and isn't a good fit for any of
  phases 2-6 as currently scoped — likely its own small phase, or folded
  into whichever phase first needs to gate real signups. Tests should keep
  creating users directly via `POST /auth/register` (bypassing this flow
  entirely), since verification doesn't block direct registration.
- **Admin roster is currently just the project owner.** Additional admins
  (e.g. teammates) are added by an existing admin promoting an account via
  `PATCH /admin/users/{id}` with `role: admin` — already supported, no new
  code needed when that happens.

## Phase roadmap

- **0 — Scaffold**: repo layout, Docker Compose, CI stub, this file.
- **1 — Auth + RBAC** (§3, §4.1): users/patients/audit_log, argon2+JWT,
  role-based authorization, login rate limiting.
- **2 — Scheduling engine + user preferences** (§4.3, §2): appointments,
  room/equipment/attending reservations, conflict-prevention via DB
  transactions/exclusion constraints, appointment state machine (including
  attending approval), persistent preferences.
- **3 — Waitlists + reminders + notifications** (§4.4): waitlist for
  cancelled/newly-available slots, background job worker for
  reminders/expiry checks, in-app notifications, MailHog-based email.
- **4 — Forum + DMs + real-time** (§2, §4.2): student community
  posts/comments/voting, private patient↔student DMs, WebSockets for live
  notifications.
- **5 — Local AI** (§1-2, §5): two distinct functions — (a) natural-language
  scheduling interpretation, where a local Ollama model only *interprets*
  requests and all final decisions are validated by deterministic backend
  logic, and (b) a separate summary/report assistant that scans historic
  data for attending/student-facing monthly/weekly reports. Do not conflate
  the two; they have different prompts, different data access, and different
  trust boundaries.
- **6 — CI/CD + Azure deploy + seed data** (§6): full CI pipeline, Azure
  deployment, seed data for demos.
