# Stu-Dent — Final Report

**Course**: Software Engineering for ML — Spring 2026
**Authors**: Yoni Oshin, Idan Peretz, Sharbel Makhoul

*(This report was drafted with AI assistance from the full build history —
the technical sections are grounded in the actual commit history, code,
and test suite. The Team Contributions section is a placeholder for the
authors to fill in.)*

## 1. Project Overview

Dental students coordinate their own patients largely over WhatsApp,
phone calls, and spreadsheets, causing scheduling conflicts, missed
appointments, and poor use of shared clinical resources (rooms,
equipment, attending dentists). Stu-Dent is a containerized web platform
centralizing patient management, appointment scheduling, shared-resource
reservation, reminders, communication (forum + direct messages), and a
local AI assistant for natural-language scheduling and historic-data
reporting — built localhost-first, fully Dockerized, with no paid
services (see `docs/proposal.md` for the original proposal).

## 2. Architecture

### Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 (sync `Session`,
  `psycopg` v3 driver), Pydantic v2, Alembic, pytest. One narrow
  exception to "no async": `app/realtime/listener.py`, a dedicated
  async Postgres LISTEN/NOTIFY task relaying real-time events to
  WebSocket clients.
- **Database**: PostgreSQL 16 — chosen specifically for transactional
  exclusion constraints (`tstzrange` GiST indexes) that prevent
  double-booking under concurrent requests without application-level
  locking.
- **Frontend**: React 19 + Vite + TypeScript, Mantine UI, TanStack
  Query, React Router v7.
- **Local AI**: Ollama (`llama3.2`), called through a single
  best-effort client (`services/ollama_client.py`) that never raises —
  every AI-touching feature degrades gracefully if the model is
  unreachable.
- **Infra**: Docker Compose (`api`, `db`, `frontend`, `mailhog`,
  `worker`, `ollama`), one documented startup command
  (`docker compose up --build`), plus a hardened production variant
  (`docker-compose.prod.yml`) for VM deployment.
- **Auth**: argon2 password hashing, JWT access tokens (HS256, no
  refresh token).

### Key design decisions

**Unified user/role model.** `users` has one `RoleEnum`
(student/attending/admin/patient) rather than separate principal types.
This reverses the original Phase 1 design (a separate `patients` table
and a second login/registration flow) — the change shipped mid-Phase-5
once real browser testing showed how awkward two login pages were in
practice. A patient gets four columns meaningful only for that role
(`owner_student_id`, `owner_confirmed_at`, `contact_phone`,
`preferred_time_of_day`); `owner_confirmed_at` is a gate *timestamp*, not
a new enum state — set immediately when a student creates a patient
directly (student vouches for them), left `NULL` when a patient
self-registers until the owning student explicitly confirms them.

**Appointment state machine.** Seven states
(`proposed → awaiting_confirmation/rescheduling_requested → confirmed →
completed/cancelled/no_show`) derived from two independent confirmation
gates (`student_confirmed_at`, `attending_approved_at`) via
`services/scheduling.py::recompute_status` — never set directly except
for terminal states. Double-booking is prevented by five Postgres
`ExcludeConstraint`s (one per resource dimension: student, patient,
attending, room, equipment), scoped to only the "active" statuses, so
concurrent requests are rejected at the database level, not through
application-level locking that could race.

**Real-time**: a Postgres LISTEN/NOTIFY bridge (`app/realtime/`) feeds a
WebSocket manager, so background-worker-originated events (reminders,
waitlist matches) reach connected clients exactly like same-process
events do — verified live via a full worker-restart test during Phase 4.

**Local AI trust boundary** (Phase 6, the project's main technical
differentiator): the model is used for two genuinely different jobs,
kept deliberately separate per the proposal's explicit instruction not to
conflate them:
- *Scheduling interpretation* (`services/scheduling_interpreter.py`):
  Ollama extracts only candidate names and date/time phrases from free
  text; every ID and every date is resolved deterministically against
  real active rows and server time (`services/nl_dates.py`) — the model
  can never assert a wrong entity or a wrong absolute date. Output only
  pre-fills the existing appointment form for human review; it never
  books anything itself.
- *Report/Q&A assistant* (`services/report_assistant.py`,
  `services/report_data.py`): a shared deterministic aggregation layer
  (`resource_utilization`, `time_impact` — plain SQL/Python math, no ML)
  computes real numbers; Ollama only narrates already-computed facts, or
  — for ad-hoc questions — classifies a question into a small fixed set
  of supported types (`resource_utilization` | `time_impact` |
  `unsupported`) and extracts a date-range phrase. It never sees the
  database or writes a query, and an unrecognized question gets a plain
  "I can't answer that yet" message rather than a guess.

Live testing against the real pulled model (not just mocked responses)
surfaced a genuine bug during Phase 6: the model sometimes returns
technically-valid JSON with a blank `"summary"` field, which was
silently producing empty-looking report cards — fixed by rejecting
blank/whitespace-only narration and falling back to raw data, with a
regression test added.

### Repo layout

```
backend/app/
  models/      SQLAlchemy ORM models
  schemas/     Pydantic request/response schemas
  core/        security (hashing/JWT), auth dependencies, rate limiting
  services/    cross-cutting helpers (audit log, notifications, scheduling, AI)
  api/routes/  FastAPI routers, one module per resource area
  jobs/        background job functions (reminders, expiry, reports)
backend/alembic/versions/   one migration per schema change, no exceptions
backend/tests/              pytest, run inside the api container
frontend/src/                Vite + React + TS
docs/proposal.md            original project proposal
docker-compose.prod.yml     hardened production stack (VM deploy)
deploy/bootstrap-vm.sh      first-time VM setup script
```

## 3. Implemented Features (by phase)

- **Phase 0 — Scaffold**: repo layout, Docker Compose, CI stub.
- **Phase 1 — Auth + RBAC**: argon2 + JWT auth, role-based authorization,
  login rate limiting backed by the audit log (no Redis/in-process
  counter), admin user management (list/detail/role change/soft delete).
- **Phase 2 — Scheduling engine**: rooms/equipment/appointment models,
  the full appointment state machine, database-enforced conflict
  prevention, student weekly availability, patient preferred time of day.
- **Phase 3 — Waitlists + reminders + notifications**: waitlist matching
  triggered by cancellations/expiry, a background worker polling for
  reminders and stale-appointment expiry, in-app notifications, MailHog
  email simulation.
- **Phase 4 — Forum + DMs + real-time** (backend-only this phase):
  student community posts/comments/voting, private patient↔student
  direct messages, WebSocket notifications backed by Postgres
  LISTEN/NOTIFY.
- **Phase 5 — Frontend**: the entire UI for phases 0-4 plus patient/admin
  views — auth, patients, appointments, availability, waitlist,
  notifications (live unread-count badge), forum, DMs, admin rooms/
  equipment/user management, patient preferences. A mid-phase detour
  unified the patient/user data model (see Architecture above) after
  real browser testing surfaced how awkward the original two-login
  design was.
- **Phase 6 — Local AI**: natural-language scheduling interpretation and
  a report/ad-hoc-Q&A assistant (see Architecture above for the trust
  boundary design). Scope was deliberately expanded beyond the original
  proposal at the team's request to include live ad-hoc Q&A, not just
  auto-generated periodic reports.
- **Phase 7 — CI/CD + seed data + VM deploy**: a full CI pipeline
  (lint, backend tests, frontend tests, Docker image build validation —
  see Testing below), an idempotent demo-data seeding script, and a
  production deployment path (hardened Docker Compose stack, VM
  bootstrap script, SSH-based deploy workflow) — built and locally
  rehearsed end-to-end; actual deployment is pending VM access from the
  course (see Deployment and Risks below).

## 4. Testing

- **180 backend tests** (pytest) across 22 test files, covering auth,
  RBAC, the appointment state machine and its conflict constraints,
  waitlists, notifications, forum, direct messages, real-time delivery,
  the scheduling interpreter and report assistant (all Ollama calls
  mocked for determinism), and the seed script's demo-data invariants.
- **27 frontend tests** (Vitest + React Testing Library) across 7 test
  files, covering the API client, date-conversion utilities, auth flows,
  and appointment-action authorization logic.
- **CI pipeline** (`.github/workflows/ci.yml`): four jobs on every push/
  PR — `lint` (ruff, black, oxlint), `backend-tests` (pytest against a
  real Postgres service container, migrations applied first),
  `frontend-tests` (Vitest + `tsc -b && vite build`), `docker-build`
  (build-only validation of all four Dockerfiles — dev and production,
  backend and frontend). A real pre-existing bug was found and fixed
  during Phase 7: the `push` trigger targeted a branch called `main`,
  which never existed on this repo (only `master` does) — so `push` had
  silently never fired since the CI stub was first added; only
  `pull_request` had ever actually run CI.
- **Testability conventions**: the standard test fixture wraps each test
  in a rolled-back transaction for isolation; a small number of tests
  that need genuine cross-connection commit visibility (real concurrency
  races, Postgres NOTIFY delivery) bypass it and use the real engine
  directly with manual cleanup.
- **Live/manual verification**: beyond automated tests, each phase's
  final milestone included a live walkthrough via browser automation
  (Claude-in-Chrome) — e.g. a full cross-role appointment lifecycle
  (student books → attending approves → student completes → patient
  views), and — for Phase 6 — genuine live tests against a real pulled
  Ollama model (not just mocked responses), which is what surfaced the
  blank-narration bug described above.

## 5. Deployment

- **Local**: `docker compose up --build` brings up the full stack
  (`db`, `api`, `worker`, `ollama`, `frontend`, `mailhog`) with one
  command, migrations applied automatically. Demo data available via
  `docker compose exec api python -m app.seed_demo`.
- **VM (course-supplied)**: the proposal's "supplied Azure environment"
  turned out, after confirming with the course lecturer, to mean a plain
  VM rather than a managed cloud platform. All deployment artifacts are
  built and were rehearsed successfully as a full local dry run
  (production Dockerfiles, `docker-compose.prod.yml`, an nginx-served
  static frontend build, a VM bootstrap script, a manually-triggered SSH
  deploy workflow) — but **actual deployment to the real VM has not
  happened yet**, since the VM itself had not been provisioned by the
  course as of this report. See Risks below.

## 6. Risks and Limitations

- **VM deployment unexecuted.** Everything is prepared and locally
  rehearsed (the full production stack was brought up locally, reusing
  the same database volume as the dev stack, and verified working
  end-to-end through the real production frontend/API), but the actual
  target machine did not exist yet at time of writing. The rehearsal did
  surface and fix two real deployment bugs (a Docker image tag collision
  between dev and prod frontend builds, and a CORS-configuration gotcha
  where forgetting to list the deploy origin produces a silent, confusing
  login failure) — both are now documented in the README.
- **No admin-approval gate on signup.** `POST /auth/register` accepts a
  `role` field with no verification — anyone can self-register as
  student, attending, or admin. This is an accepted simplification for a
  course project (called out in the README), not something fixed
  unprompted; a real identity-verification + admin-approval flow is
  documented as a backlog item but wasn't scheduled to any phase.
- **The VM deploy plan hasn't been validated against a real network/
  firewall setup.** `docker-compose.prod.yml` doesn't expose Postgres or
  Ollama outside the VM's own Docker network at all (only the frontend,
  API, and MailHog's ports are published) — a reasonable default, but
  whatever firewall/security-group rules the actual VM enforces at the
  network level are outside this project's control and unverified until
  the real VM exists.
- **Local AI is best-effort, not guaranteed.** Both AI features degrade
  gracefully (plain warnings / raw-data fallback) if Ollama is
  unreachable or the model isn't pulled — this is a deliberate design
  choice (the proposal explicitly requires all final scheduling decisions
  to be validated by deterministic backend logic, not the model), but it
  does mean the AI features' output quality varies with whatever local
  model is actually running.
- **Non-goals honored, not gaps**: no diagnosis/treatment
  recommendation by the AI, no real EHR integration, no native mobile
  app, no paid third-party services anywhere in the stack — all
  intentional per the original proposal's explicit non-goals.

## 7. Team Contributions

*(Placeholder — to be filled in by the authors: Yoni Oshin, Idan Peretz,
Sharbel Makhoul.)*
