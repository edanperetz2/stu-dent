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
  different command — and `ollama`, added in Phase 6), one startup command,
  `.env.example`.
- Auth: argon2 password hashing (`argon2-cffi`), JWT access tokens (`PyJWT`,
  HS256, no refresh token).
- Local AI: Ollama (`llama3.2` by default), called only through
  `services/ollama_client.py` — see Phase 6's roadmap entry for the trust
  boundary this enforces.

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

Seed demo data (idempotent, safe to re-run):
```powershell
docker compose exec api python -m app.seed_demo
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
  appointments, availability (removed post-submission, see below —
  never really used), waitlist, notifications (with a live
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
- **7 — CI/CD + seed data** (§6): done. **Full CI pipeline** —
  `.github/workflows/ci.yml` fixed a real pre-existing bug (the `push:`
  trigger targeted branch `main`, which never existed; the repo's only
  branch is `master`, so `push` had silently never fired, only
  `pull_request` ever ran CI) and gained `frontend-tests` (vitest +
  `tsc -b && vite build`, previously never run in CI at all) and
  `docker-build` (build-only validation of both Dockerfiles).
  **`backend/app/seed_demo.py`** — idempotent (checks for a sentinel demo
  admin email, no-ops if already seeded), mirrors `worker.py`'s
  `python -m app.<module>` invocation pattern, reuses real service
  functions (`validate_participants`/`recompute_status`,
  `services/notifications.py::notify`,
  `services/report_assistant.py::generate_periodic_report`) rather than
  hand-crafting rows, so demo data respects the same invariants real data
  would. Live-verified: seeded data renders correctly across
  Patients/Appointments/Forum/Reports/Notifications, and the seeded
  weekly report gets genuinely narrated by Ollama referencing the actual
  seeded entities. `docs/final_report.md` (architecture, features,
  testing, risks; team contributions left as a placeholder for the
  authors) and `docs/demo_video_script.md` (a timed walkthrough script
  covering every required workflow, using the seeded demo accounts) are
  both drafted and committed, frozen as of course submission (see the
  note at the top of the post-submission section below); recording the
  actual video is still the user's to do.
- **Codebase review + cleanup (cross-phase, not a proposal-scoped phase)**:
  **done**. A full scan of every phase's code (backend, frontend,
  infra/CI/docs) via 3 parallel research passes produced 29 concrete,
  file:line-cited findings — pure improvements (efficiency, explainability,
  comfort/DX/accessibility), explicitly never changing behavior or scope.
  Implemented in 4 batches, each tested and CI-verified green before the
  next started: **(1) infra/CI/docs** (`fe39079`) — Node 20→22, pip/npm/
  Docker-layer CI caching, a couple of stale README/comment fixes, the
  `docker-compose.prod.yml` frontend healthcheck (with the IPv4-vs-IPv6
  `wget`/`localhost` gotcha fixed along the way) — `docker-compose.prod.yml`
  itself was later deleted entirely by `a311dd0` once the VM deploy was
  descoped, so this healthcheck fix no longer exists in the current repo;
  left here as historical record of the batch, not something to go re-apply.
  **(2) backend efficiency
  + dedup** (`24f23a7`) — added indexes (`appointment.end_time`, a
  composite `audit_log` index), collapsed an N+1 existence-check loop in
  `jobs/reports.py` into one batched query, added
  `services/scheduling.py::is_visible_to_participant` and
  `database.py::get_or_404` (PEP 695 generic) to dedupe near-identical
  per-route helper functions, added `services/users.py::active_user_filters`
  to dedupe the repeated active/non-deleted role-filter predicate. **(3)
  frontend efficiency** (`b2c6bdf`) — converted `AppRouter.tsx`'s ~19 page
  imports to `React.lazy()` + `Suspense` (main bundle 657KB→355KB, killed
  the "chunk larger than 500kB" build warning), memoized `AuthContext`'s
  context value and a couple of derived option lists. **(4) frontend
  comfort/DX + accessibility** (`9697730`) — added `apiErrorMessage()` and
  `LoadingText`/`EmptyText` (`components/StateText.tsx`) to dedupe the
  identical error-ternary and loading/empty-state `<Text>` repeated across
  nearly every page; added keyboard navigation (`tabIndex`/`role`/
  `onKeyDown`) to the 5 clickable-table-row pages that only responded to
  mouse clicks (appointments, patients, forum lists + both detail-page
  variants already had it); added a missing `aria-label` to the
  availability page's icon-only delete button; deduped the repeated
  auth-test `beforeEach` reset into `test/resetAuthTestState.ts`. All 4
  batches' full regressions (backend pytest/ruff/black; frontend tsc/
  oxlint/vitest/build) passed and all 4 pushes are green on GitHub Actions.
- **Post-submission feature work (cross-phase, ongoing)**: the report and
  video script above are frozen as of course submission; real work
  continued afterward and is tracked here instead of by editing those
  submission artifacts. In rough order: patient preferences show the
  in-charge student's name (`85adeb1`, `owner_student_name` resolved only
  on `GET/PATCH /users/me`); messaging was redesigned twice — first
  (`a945ef7`) from an implicit patient-keyed `direct_messages` table to a
  real `conversations`/`conversation_participants`/`messages` model
  supporting student↔attending, a shared admin inbox, and student/
  attending group chats (destructive migration, dev data only), then
  again (`e9beb14`) adding per-conversation unread badges with
  unread-first/most-recent sort and auto-mark-read-on-open, a tweet-style
  forum feed replacing the table listing (inline expand, combined toggle
  like/dislike counters), and removing the never-really-used weekly
  student-availability feature end-to-end; a day/week/month appointment
  calendar was added alongside the existing table
  (`dd9fd32`, react-big-calendar) with click-empty-slot-to-create and
  click-event-to-edit; room became mandatory on every appointment
  (`ab81a5d`) with patient-initiated (room-less) requests requiring the
  accepting student to assign one, plus an admin room-as-resource
  calendar and scheduled (date-limited) room/equipment deactivation
  auto-reactivated by `jobs/reactivation.py`; equipment gained the same
  double-booking/deactivation parity rooms already had, plus a
  clinic-wide anonymized "Resources" list/calendar view
  (`0b4db58`, `GET /resources/schedule`) for students/attendings (full
  detail for admin, personal-only for patients); a logo and assorted UI
  polish were added (`78343ba`); `.gitattributes` now pins `*.sh` to LF
  (`15b29b8`) after a Windows `core.autocrlf` checkout corrupted
  `backend/entrypoint.sh`'s shebang and crashed the `api`/`worker`
  containers.
  **Waitlist redesign** (this session, largest single change in this
  arc): replaced the old near-duplicate-of-`Appointment`,
  manually-filled waitlist with one that only exists in reaction to a
  real, explained booking failure. New `services/scheduling.py::
  find_conflicts` runs a targeted per-resource-type query (student,
  patient, and — when supplied — attending/room/equipment) instead of
  relying on a generic Postgres exclusion-constraint error with no way
  to know which of the 5 constraints fired; `create_appointment`,
  `update_appointment`, and `accept_appointment`'s room-change path all
  call it pre-emptively and raise a new `AppointmentConflictError` (409
  + a `conflicts: ConflictReason[]` array naming the exact blocking
  resource) instead of relying solely on the DB-level `flush_or_409`
  safety net (still in place for genuine races).
  `WaitlistEntry` gained `conflict_resource_types` (why this entry
  exists), `notes`, `student_confirmed_at` (so auto-promotion can hand
  off to the same `recompute_status` real bookings use instead of
  fabricating a confirmation), and a monotonic `sequence` column
  (`Identity()`, same fix as `Message.sequence` — Postgres freezes
  `func.now()` within one transaction, so `created_at` alone can tie).
  `services/waitlist.py::recheck_waitlist_after_cancellation` re-runs
  `find_conflicts` per candidate ordered by `sequence` (first-come-
  first-served; a losing entry keeps its place ahead of newer ones for
  the next opportunity) and promotes a fully-cleared entry into a real
  `Appointment` inside a `db.begin_nested()` savepoint (not a bare
  flush — the caller's own pending cancellation must survive a losing
  race). Frontend gained a shared `ConflictResolutionModal` (used from
  the create, edit, and accept flows) offering "adjust and retry" or
  "join the waitlist with this exact request"; `WaitlistPage` is now a
  log of real attempts (cause badges, status, link to the resulting
  appointment) rather than a manual creation form.
  Four gaps were found and fixed before commit via explicit user
  pre-commit review: (1) the attending (not just student/patient) now
  gets notified when their waitlist entry auto-promotes; (2) promotion
  ordering was non-deterministic under a full-suite pytest run because
  same-transaction rows tied on `created_at` — fixed by the `sequence`
  column above; (3) a real medical-confidentiality gap — a patient
  requesting a slot could see their conflict was caused by "student"
  busy, revealing their own student was occupied by a *different*
  patient's care — fixed by `redact_conflicts_for_patient`, which
  collapses `student`/`patient` causes into one generic self-referential
  `patient` cause for a patient viewer only (student/attending/admin
  viewers of the identical data still see the real cause; confirmed with
  the user that attending/room/equipment names should stay specific,
  not generalized further); (4) realtime WebSocket notifications now
  also invalidate the `appointments`/`waitlist`/`resources` query caches
  (previously only `notifications`), so an auto-promoted appointment
  appears without a manual refresh.
  A follow-up gap surfaced by live user testing after the above: editing
  an existing appointment into a conflicting slot and choosing to join
  the waitlist left the *original* appointment still active — the user
  chose (over the safer "cancel once the waitlist resolves" option) to
  cancel it immediately on joining, so `ConflictResolutionModal` gained
  a `cancelsExistingAppointment` prop (red "Cancel & join waitlist"
  button + explicit warning, used from the edit/accept flows only, not
  plain create) and `AppointmentDetailPage`'s join-waitlist mutation now
  chains an immediate `cancelAppointment` call on success.
  Same session, three smaller fixes: cancelled appointments no longer
  appear in the appointments list or calendar (filtered client-side in
  `AppointmentsListPage`; still reachable directly by ID, e.g. from a
  notification link) — DB rows are kept, not hard-deleted, per this
  file's soft-delete convention; verified editing an appointment into a
  *free* slot updates the same row in place (same ID, same total count),
  not a new one; and the appointment start/end `DateTimePicker`s (whose
  free-typed hour/minute spinner was hard to drive correctly) were
  replaced by a new shared `components/AppointmentDateTimeInput.tsx` —
  a plain date-picker plus a fixed half-hour `Select`
  (`APPOINTMENT_START_TIME_OPTIONS`/`_END_TIME_OPTIONS` in
  `utils/dates.ts`: 08:00–21:00 / 08:30–21:30) — tracking date and time
  in separate local state so picking one doesn't discard the other
  before both are set.
