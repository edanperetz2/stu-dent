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
  driver for all request/route/job code — no async there, not needed).
  Phase 4 adds one narrow exception: a dedicated async Postgres
  LISTEN/NOTIFY task (`app/realtime/listener.py`) using `psycopg`'s native
  `AsyncConnection` support (no new dependency) to relay real-time events to
  WebSocket clients — this is isolated to that one task, not a general
  async migration.
  Pydantic v2, Alembic, pytest.
- DB: PostgreSQL 16. Chosen because later phases need transactions and
  range/exclusion constraints to prevent double-booking (§4.3).
- Frontend: React + Vite + TypeScript.
- Infra: Docker Compose (`api`, `db`, `frontend`, `mailhog`, `worker` — the
  worker shares the `backend` image/build context with `api`, just runs a
  different command), one startup command, `.env.example`.
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
- **One `users` table, one role enum — patient is a 4th role, not a
  separate principal type.** This reverses the original Phase 1 design
  (two separate tables/login endpoints); the change shipped after Phase 5
  Milestone 3 once real browser testing surfaced how awkward the
  two-login-page/two-registration-page split was for actual use. `users`
  gains four columns meaningful only when `role == patient`:
  `owner_student_id` (self-FK — the treating student), `owner_confirmed_at`
  (nullable timestamp gate — see below), `contact_phone`,
  `preferred_time_of_day`. There is one `/auth/register` and one
  `/auth/login` for every role; `LoginIn.role` is an optional hint the
  backend actually validates against the account's real role, not just a
  frontend affordance. `core/deps.py` has a single `get_current_user`
  dependency — no more `get_current_patient`/`get_current_principal`/
  `Principal` dispatch. Paired dual-principal columns collapsed to one
  each: `audit_log.actor_id`, `notifications.recipient_id`,
  `direct_messages.sender_id`.
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
- **Two patient onboarding paths (post-unification), both live**:
  (1) *student-initiated* — `POST /patients` now takes `full_name`, `email`,
  `password` up front (a patient is a real `users` row from the moment it
  exists) and is auto-confirmed immediately (`owner_confirmed_at = now()`),
  since the student vouched for it; (2) *patient self-registration* — a
  patient registers via the same unified `/auth/register` with
  `role: patient` and `owner_student_id` set to a student picked from the
  public `GET /students` directory, but this leaves `owner_confirmed_at`
  `NULL` (pending) until the owning student calls
  `POST /patients/{id}/confirm`. An unconfirmed patient can log in and read
  their own profile but is blocked (403 via
  `services/patients.py::require_confirmed_patient`) from creating
  appointments/waitlist entries/DMs. Registering as a pending patient
  notifies the chosen student (`NotificationType.patient_registration_request`)
  through the existing Phase 3/4 notification pipeline.
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
- **4 — Forum + DMs + real-time** (§2, §4.2): **backend-only**, same as
  phases 0-3 — student community posts/comments/voting (students
  create/read/comment/vote; admin reads and moderates; attending/patient
  have no forum access — judged from proposal wording, not asked), private
  patient↔student DMs, WebSockets (backed by Postgres LISTEN/NOTIFY so
  worker-originated events reach connected clients too) for live
  notifications. The frontend UI for this phase, and for everything built
  so far, is explicitly deferred to Phase 5.
- **5 — Frontend** (whole app so far): **done**. The first real frontend
  work — the frontend was an untouched Vite scaffold through phases 0-4.
  Covers auth (unified login/register, role-aware routing), patients,
  appointments, availability, waitlist, notifications (with a live
  unread-count badge), forum, DMs, admin rooms/equipment/user management,
  and patient preferences — all with live updates over the Phase 4
  WebSocket where relevant. Built across 7 milestones plus a mid-phase
  detour (after milestone 3) to unify patients into the `users`/role
  model — see the "one `users` table, one role enum" convention bullet
  above. Milestone 7 closed the phase with a full automated regression
  (backend pytest/ruff/black, frontend tsc/oxlint/vitest/build) plus a
  live cross-role appointment-lifecycle walkthrough (student books with
  an attending assigned → attending approves → student completes,
  checked from all three roles' views) via a browser-automation MCP tool.
- **6 — Local AI** (§1-2, §5): **done**. Two distinct functions, kept
  deliberately separate — (a) natural-language scheduling interpretation:
  `services/scheduling_interpreter.py` asks Ollama for candidate names and
  a date/time phrase only; every ID and every date is then resolved
  deterministically against real active rows and server time
  (`services/nl_dates.py`), never trusted verbatim from the model.
  `POST /scheduling/interpret` pre-fills the existing appointment
  create-form (`form.setValues`) for human review — it never books
  anything itself, so `services/scheduling.py`'s validation still gates
  every real submit. (b) a summary/report assistant, scoped larger than
  originally proposed at the user's explicit request: auto-generated
  weekly/monthly reports **plus live ad-hoc natural-language Q&A**, both
  built on one shared deterministic aggregation layer
  (`services/report_data.py`: `resource_utilization`,
  `time_impact` — plain SQL/Python math, no ML). The ad-hoc path
  (`services/report_assistant.py::answer_ad_hoc_question`) is the
  narrower of the two AI surfaces on purpose: the model only ever
  classifies a question into a small fixed set of supported types
  (`resource_utilization` | `time_impact` | `unsupported`) and extracts a
  date-range phrase — it never sees the database or writes a query, and
  an unsupported question gets a plain "I can't answer that yet" message
  rather than a guess. `jobs/reports.py` generates each user's
  weekly/monthly report once per calendar period (existence-check
  idempotent, wired into `worker.py`), and `POST /reports/generate` +
  `POST /reports/ask` cover manual/on-demand generation from the new
  `ReportsPage`. `ollama_client.py` is the single, best-effort
  (never-raises) boundary both features call through — if Ollama is
  unreachable or a model isn't pulled, both paths degrade gracefully
  (plain warnings / raw-data fallback) instead of erroring. Built across
  6 milestones (Ollama infra + NL interpreter backend, NL interpreter
  frontend, report data + periodic reports backend, ad-hoc Q&A backend —
  ended up folding into the same milestone as periodic reports since they
  share `report_assistant.py`/`report_data.py`, reports frontend, full
  regression + live verification). Requires a one-time
  `docker compose exec ollama ollama pull <model>` after first `docker
  compose up` — models aren't baked into the `ollama/ollama` image.
- **7 — CI/CD + VM deploy + seed data** (§6): in progress. Proposal §6's
  "supplied Azure environment" turned out (confirmed with the course
  lecturer) to mean a plain VM, not a managed cloud platform — the user
  has sent their SSH public key and is waiting on the VM to actually be
  provisioned. **Done for real, zero cost/credentials needed**: (a) full
  CI pipeline — `.github/workflows/ci.yml` fixed a real pre-existing bug
  (the `push:` trigger targeted branch `main`, which never existed; the
  repo's only branch is `master`, so `push` had silently never fired,
  only `pull_request` ever ran CI) and gained `frontend-tests` (vitest +
  `tsc -b && vite build`, previously never run in CI at all) and
  `docker-build` (build-only validation of all four Dockerfiles, dev and
  prod). (b) `backend/app/seed_demo.py` — idempotent (checks for a
  sentinel demo admin email, no-ops if already seeded), mirrors
  `worker.py`'s `python -m app.<module>` invocation pattern, reuses real
  service functions (`validate_participants`/`recompute_status`,
  `services/notifications.py::notify`,
  `services/report_assistant.py::generate_periodic_report`) rather than
  hand-crafting rows, so demo data respects the same invariants real data
  would. Live-verified: seeded data renders correctly across
  Patients/Appointments/Forum/Reports/Notifications, and the seeded
  weekly report gets genuinely narrated by Ollama referencing the actual
  seeded entities. **Prepared, locally rehearsed, not yet run against a
  real VM** (which doesn't exist yet): `docker-compose.prod.yml`
  (standalone file, not a compose override — every dev service hardened
  for production: prod Dockerfiles, no bind-mounts/`--reload`,
  `restart: unless-stopped`; unlike the Container-Apps plan this
  replaced, Ollama stays in since a VM's cost model is flat, not
  pay-per-container-second), `backend/Dockerfile.prod`,
  `frontend/Dockerfile.prod` + `frontend/nginx.conf` (multi-stage,
  SPA-fallback routing), `deploy/bootstrap-vm.sh`,
  `.github/workflows/deploy.yml` (`workflow_dispatch`-only, structurally
  inert until VM secrets are configured). Also added CORS multi-origin
  support (`frontend_origins` comma-separated setting +
  `frontend_origin_list` property) since a real deploy needs to allow
  both `localhost` and the VM's own origin. **The full prod stack was
  actually rehearsed locally** (stopped the dev stack, brought up
  `docker-compose.prod.yml` reusing the same named Postgres volume so the
  seeded demo data carried over, logged in through the real nginx-served
  frontend against the real prod API) — this caught and fixed two genuine
  bugs a review alone wouldn't have: (1) the prod `frontend` service had
  no explicit `image:` tag and silently collided with/overwrote the dev
  stack's implicit `finalproject-frontend` image tag — fixed by giving it
  an explicit distinct tag; (2) forgetting to add the deploy origin to
  `FRONTEND_ORIGINS` produces a confusing silent "login failed" with no
  visible error (the browser blocks the cross-origin request client-side)
  — now documented prominently in the README's VM deploy section.
  **Resume next**: once the VM exists, SSH in, run
  `deploy/bootstrap-vm.sh`, configure `.env` with the VM's real address,
  bring up `docker-compose.prod.yml` for real, optionally wire up
  `deploy.yml`'s secrets.
