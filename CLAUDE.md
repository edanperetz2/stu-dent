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
- **Frontend UX/accessibility remediation (cross-phase, friend-review-driven,
  13 milestones)**: **done**. Triggered by a friend's frontend-weighted
  code review of the whole project (`docs/stu-dent-review.html`); two
  independent verification passes confirmed 15 of 16 spot-checked claims
  exactly or near-exactly true (the one inflated metric was a grep miscount,
  not a real finding), so the review was trusted and acted on in full — the
  user chose the broadest offered scope (P0 + P1 + P2 + visual + UX) plus
  two features the review had flagged as "decide later": a real
  forgot-password flow and a real dark mode (previously just
  `color-scheme: light dark` in CSS with no Mantine wiring). Executed as 13
  milestones, each implemented/tested/live-verified and stopped for
  explicit go-ahead before the next, per this file's established milestone
  workflow — no commits without being asked, same as always. In order:
  **M1** shared primitives (`useMutationWithToast`, `PageHeader`,
  `ClickableRow` — a real focusable button in its own cell instead of the
  `role="button"`-on-`<Table.Tr>` hack 5 pages used, which broke the row's
  implicit semantics and was keyboard-unreachable). **M2** real error states
  (not silently-empty ones) rolled out to the 11 pages + 3 `AppLayout`
  badge queries that were still missing `ErrorText`/retry. **M3**
  session-expiry handling: `httpClient.ts` now redirects to `/login` on a
  401 with the attempted destination preserved instead of retrying
  pointlessly forever; `JWT_EXPIRE_MINUTES` raised 30→120 in
  `.env.example` (shorter than a clinic shift, previously). **M4**
  WebSocket resilience — exponential backoff with a cap, a manual
  reconnect control once retries are exhausted, and a connection-status
  pill in the header (the `isConnected` state had zero call sites before
  this). **M5** sidebar nav rebuilt as real `<Link>`s with icons and
  `aria-current`, replacing `onClick`-only items with no real `href` a
  keyboard user couldn't reach at all. **M6** accessibility pass: `Alert
  role="alert"` for form/page errors, ARIA-live status regions,
  `ClickableRow` rolled out everywhere. **M7** forgot-password, built for
  real: `password_reset_tokens` table, SHA-256-hashed single-use tokens
  (not argon2 — reserved for low-entropy human passwords), two-layer
  per-email+per-IP rate limiting, enumeration-resistant responses, email
  delivered through the existing MailHog pipeline. **M8** theme system —
  brand color derived from the logo hex instead of stock Mantine blue, a
  real `defaultColorScheme="auto"` dark mode with an anti-FOUC inline
  script (Mantine's own `<ColorSchemeScript>` doesn't apply to a
  client-rendered SPA with no SSR), status-badge colors redesigned around
  one uniform ink text color after hand-verifying several "obviously fine"
  combinations actually failed WCAG AA contrast math. **M9** split the
  901-line `AppointmentsListPage` into `PersonalAppointmentsTable`,
  `ResourceAppointmentsTable`, `AppointmentsCalendarView`,
  `resourceColors.ts`, and `useAppointmentActions` (504 lines left,
  orchestration only). **M10** calendar `min`/`max`/`scrollToTime` bounds
  (derived from the same time-option constants the booking form already
  used, not hardcoded a second time) and a full New Appointment modal
  rebuild — grouped `Fieldset`s, duration-shortcut chips that compute an
  end time directly instead of a second manual pick, the AI describe box
  moved behind a toggle instead of occupying the top of the modal, a
  pinned submit footer; all 16 `<Modal>` call sites across the app given
  an explicit `size` for the first time. **M11** server-side pagination —
  `GET /appointments` gained date-range/status/limit/offset params (the
  Calendar sub-view now only fetches what's on screen instead of
  everything ever booked), notifications got real `useInfiniteQuery`
  pagination (and, since the naive `.length`-of-a-page badge count would
  have silently undercounted past the new page size, a proper `GET
  /notifications/unread-count` endpoint instead), and
  `list_conversation_messages` — which previously had no cap at all —
  gained `limit`/`before_sequence`; `autoComplete` added across the real
  gaps (RegisterPage, New Patient, patient/preferences phone fields); the
  login page's Role dropdown removed (the backend already validates role
  against the real account, so the picker could only ever turn a valid
  login into a spurious failure). **M12** motion + P2 polish — shaped
  `Skeleton` placeholders replacing bare "Loading…" text everywhere (`LoadingText`
  itself deleted once unused), table row expansion switched from an
  instant conditional render to an animated `Collapse` (with
  `keepMounted={false}` so a collapsed `AppointmentDetailPanel` doesn't
  stay mounted with live queries for every row at once), a
  `prefers-reduced-motion`-aware fade-in for genuinely-new list rows,
  search/status-filter/sort added to the Personal-lens appointments table,
  and undo-toasts for **only** the actions where a delayed undo is
  provably safe: deactivating a user and cancelling a waitlist entry
  (pure status flips, no side effects) — appointment cancel/reject
  deliberately kept its real confirm-modal instead, because cancelling
  synchronously auto-promotes a *different* waitlist entry into a real
  booking, and a delayed undo could then collide with that new
  appointment; the waitlist-cancel undo needed a small new `POST
  /waitlist/{id}/reactivate` endpoint since no un-cancel capability
  existed. **M13** full regression + live verification closed the arc,
  and caught two real bugs in the M12 work that a plain test-suite pass
  wouldn't have: Mantine's own `<Modal>` close button ships with no
  `aria-label` at all in this version (a screen reader hears bare
  "button") — fixed once, for all 16 modals, via a `Modal.extend()`
  theme-level default rather than 16 individual edits; and `UsersPage`'s
  deactivate-then-undo toast fired both requests without waiting for the
  first to settle, so a fast undo click could race the original request
  and leave the UI showing the wrong state — fixed by having the undo
  handler `await` the original `mutateAsync` before re-mutating (the
  equivalent waitlist code turned out to already be safe, since that
  toast was shown from `onSuccess`, not from the click handler itself).
  Full live verification also covered a keyboard-only pass, a dark-mode
  toggle check, forgot-password end-to-end through MailHog, session-expiry
  triggered for real (temporarily set `JWT_EXPIRE_MINUTES=1`, confirmed
  the redirect-with-banner flow, reverted), WebSocket reconnect (stopped
  and restarted the `api` container mid-session, watched the
  disconnect/reconnect indicator), and a full cross-role booking
  walkthrough on the rebuilt modal (student books with an attending
  assigned → attending approves → student completes).
  **M14 (follow-up)**: after M13, a line-by-line cross-check of the actual
  codebase against `docs/stu-dent-review.html` itself (not against this
  plan) found 5 items the review asked for that M1-13 hadn't actually
  landed. All 5 fixed: the calendar's fixed `height: 700` became a
  viewport-derived height plus an Agenda view offered on narrow screens;
  `PersonalAppointmentsTable` cut from 8 columns to 4 (Time/Status/People/
  Where), dropping the viewer's own name (whichever of student/patient/
  attending the signed-in principal is), day-grouping rows when
  chronologically sorted, and replacing bare `'—'` with real absence
  labels; the two hand-maintained `STATUS_BADGE_BACKGROUND`/
  `STATUS_CALENDAR_COLOR` hex maps in `appointmentActions.ts` became one
  hue-per-status table, generating both the pale badge and saturated
  calendar shades via `theme.ts`'s `hslToHex` (now exported) — the
  saturated shade's lightness is the max that clears WCAG AA (4.5:1)
  against white text, found per-hue by binary search at module load rather
  than hand-picked; this also caught a real, previously-unverified AA
  failure (`proposed`'s shipped `#868e96` measured ~3.3:1) that the
  earlier hand-fix (`#f59f00` → `#8a6100`) hadn't covered since it only
  touched the two statuses the review specifically named. A new
  `useListQuery` hook (`src/hooks/useListQuery.ts`) turns the
  loading/isError/data ternary hand-copied across pages into one
  discriminated union a page switches over — `result.data` only
  type-checks inside the `'ready'` branch, so a page can't reach the list
  while skipping the error branch and still compile; retrofitted onto the
  8 pages whose primary query is a single plain `useQuery` driving the
  page's main content (Patients, Forum, Rooms, Equipment, Users, Waitlist,
  Preferences, Appointments) — `MessagesPage` (three independent queries
  rendered separately), `NotificationsPage` (`useInfiniteQuery`, a
  different data shape), `ForumPostCard` (its comments query is
  conditional on being expanded, not page-level), and `RegisterPage` (its
  students query feeds a `Select`'s placeholder/disabled state, not a
  full-page render branch) were deliberately left alone rather than forced
  into a shape that didn't fit. Inline `style={{}}` usage (19 occurrences
  across 10 files, up from the review's cited 11) was triaged rather than
  blanket-removed: repeated `cursor: pointer` and `white-space` patterns
  collapsed into 3 small CSS classes; `flex`/`minWidth`/`maxHeight` cases
  converted to Mantine's `flex`/`miw`/`mah` shorthand props; what's left
  (dynamic per-row colors, a react-big-calendar library prop, `align-self`
  and single-side `border`, neither of which Mantine exposes as a
  shorthand) each got a one-line comment explaining why it stays inline,
  down to 10 documented occurrences. Full regression green throughout
  (tsc, oxlint, vitest — 98/98 across 28 files, up from 94 — and
  `vite build`, no bundle-size warning).
  **M15 (follow-up, scoped down)**: a second post-M13 review cross-check
  found 3 more review action items not literally satisfied — before
  implementing any of them, each was evaluated for actual benefit rather
  than implemented on the review's say-so alone (a correction from how
  M14 was approached). Verdict: server-side status filtering for
  `/appointments` and a real infinite-scroll UI for the appointments List
  sub-view were judged not worth doing — the endpoint is already bounded
  (date-range for Calendar, a 500-row default `limit` for List) so
  client-side filtering of what's already fetched is a lateral move at
  best, and building real pagination UI without also moving the
  client-side search/sort server-side would make the existing sort
  feature *worse* (correct only within whatever page happened to be
  loaded) — a real risk, not just unnecessary effort. Only the third item
  was implemented: dedicated tests for the four pieces M9 extracted from
  `AppointmentsListPage` (`PersonalAppointmentsTable`,
  `ResourceAppointmentsTable`, `AppointmentsCalendarView`,
  `useAppointmentActions`), none of which had any coverage of their own
  before this — real regression protection for code the M14 table
  redesign had just modified. 15 new tests (viewer's-own-name dropping,
  day-grouping, absence labels, admin-vs-non-admin resource columns, the
  409-conflict-opens-a-modal branch, the narrow-screen Agenda view, the
  responsive height formula). Full regression green (tsc, oxlint, vitest
  — 113/113 across 32 files — `vite build`).
  **M16 (quality audit + fixes)**: after M15, three parallel agents did an
  adversarial code-quality pass (not presence/absence) over everything
  implemented across this whole review-remediation arc — tracing logic,
  not grepping for keywords. Found 4 real, concrete defects, all fixed:
  (1) status badges (`appointmentActions.ts`, `WaitlistPage.tsx`) were
  hardcoded to a pale-background/dark-ink pairing regardless of theme, so
  every badge rendered as a bright near-white pill in dark mode — both
  now generate a dark-mode variant (reusing the already-AA-verified
  saturated `STATUS_CALENDAR_COLOR` shade + white text) picked via
  `useComputedColorScheme()`, and the shared contrast-math binary search
  moved to `utils/colorContrast.ts` so `WaitlistPage`'s own 3-status table
  doesn't hand-roll a second copy. (2) the narrow-screen Agenda calendar
  view visually spans react-big-calendar's default 30 days, but the
  underlying query was still scoped to the current week — days 8-30
  silently showed nothing, indistinguishable from "no appointments";
  fixed by passing `length={7}` to `<Calendar>` and adding a matching
  `'agenda'` case to `getCalendarViewRange` (`resourceColors.ts`) so the
  two can't drift apart again. (3) the backend closed the WebSocket with
  the same code for "token genuinely rejected" and "no auth message
  arrived within the 10s timeout" (`websocket.py`), but the frontend
  treats that code as a hard session-expiry logout — a slow/congested
  connection (not an actually-expired session) could log a user out;
  the timeout/malformed-message path now closes with
  `WS_1002_PROTOCOL_ERROR` instead, leaving `WS_1008_POLICY_VIOLATION`
  for genuine rejection only (2 new backend tests assert the distinction
  directly). (4) `UsersPage`'s Deactivate/Activate/Delete/role-change
  actions all read one shared mutation's `isPending`/`variables` to decide
  which row's spinner to show — correct for one action at a time, but two
  different rows acted on within moments of each other could show a
  stale/wrong spinner, since the shared mutation's state only reflects the
  most recently fired call; fixed with per-row `Set<string>` pending-id
  tracking (`togglePending`) independent of the mutation object's own
  state. Two lower-severity findings from the same audit were reported but
  deliberately left as-is: `useListQuery`'s unused `enabled` option (no
  live call site passes it, so the theoretical gap it could cause isn't
  reachable today) and the same shared-mutation display-state pattern
  existing in `RoomsPage`/`EquipmentPage`/`WaitlistPage` too (not fixed
  here since it wasn't the specific finding flagged — noted as a known
  parallel, not addressed). Full regression green across both stacks:
  backend pytest (297/297, including the 2 new websocket tests), ruff,
  black; frontend tsc, oxlint, vitest (113/113), `vite build`.
- **Comprehensive 0-100 audit + fix arc (cross-phase, this session)**:
  **done**. At the user's explicit request for "the most coverage audit
  you can — not excluding nothing, nothing out of scope," 10 parallel
  subagents plus personal verification of every P1 claim scanned the
  entire repo (backend, frontend, infra/CI/docs — zero exclusions) and
  produced 15 P1s, ~30 P2s, and 1 confirmed structural bug. Fixed via a
  16-batch, dependency-ordered plan (migration integrity first since
  later batches' CI step depends on it; `useListQuery` isolated in its
  own batch given its 8-page blast radius; docs/ruff-`S`/TS-`strict`/
  coverage held for explicit scope decisions rather than assumed):
  **(1)** named 7 unnamed `drop_constraint` calls and fixed an enum
  `create_type=False` gap in `c29f7803b629`'s `downgrade()`, verified via
  a real upgrade→downgrade→upgrade round-trip. **(2)** CI gained an
  Alembic downgrade/upgrade round-trip step and a `dependency-audit` job
  (pip-audit + npm audit, one documented CVE allowlist entry), 5
  GitHub Actions SHA-pinned; `conftest.py` switched from
  `Base.metadata.create_all()` to running real migrations. **(3)**
  `update_appointment` now resolves the *old* attending's stale
  notification on reassignment/clear; `accept_appointment` runs
  `find_conflicts` unconditionally, not just when the room changed.
  **(4)** waitlist auto-promotion now calls `validate_participants` before
  promoting (can't book a since-deactivated resource); resource
  deactivation now notifies pending-waitlist students, not just booked
  ones. **(5)** `scheduling_interpreter.py` guards every raw Ollama field
  against a non-string crash; an unresolved date-range phrase gets its
  own honest message instead of a silent 30-day fallback;
  `jobs/reports.py::_period_bounds` converts through `DISPLAY_TIMEZONE`
  like `nl_dates.py` already did. **(6)** `useListQuery` reordered so a
  failed background refetch no longer discards already-loaded valid data
  — given its own dedicated regression test and full-suite verification
  pass. **(7)** `showUndoToast`/`ConfirmButton` given defensive
  catch/await fixes (later found incomplete, see below). **(8)** forum
  votes and **(9)** register/patient-create duplicate-email races now use
  the same `db.begin_nested()` + `IntegrityError` rescue pattern as
  `get_or_create_conversation`; admin blocked from role-flipping a user
  into/out of `patient`; a malformed JWT subject now 401s instead of
  500ing. **(10)** `ollama`/`mailhog` images pinned by digest, `ollama`
  bound to localhost, `/health` actually checks the DB. **(11)**
  `docs/final_report.md`/`docs/proposal.md` corrected to stop describing
  the already-deleted VM-deploy path in the present tense. **(12-13)**
  ruff's `S` (flake8-bandit) ruleset and TypeScript `strict` both enabled
  clean. **(14-16)** ~90 new tests closing every zero-coverage file the
  audit found (pages, shared components, hooks/utils/API clients).
  Two independent adversarial re-reviews followed, each spawning fresh
  subagents told not to trust prior claims and to re-verify against the
  live code: the **first** (of commit `a11025c`) found 4 real gaps —
  `report_assistant.py` collapsing two genuinely different Ollama failure
  messages into one `content_source` (fixed with a new
  `malformed_response` enum value + migration `c8e31c7b13c1`); `deps.py`
  missing `AttributeError` in its malformed-JWT-subject guard;
  `showUndoToast` only catching a *rejecting* `onUndo`, not a
  *synchronously throwing* one; `ConfirmButton`'s await-before-close fix
  only working where the caller actually returned a promise (`UsersPage`'s
  Delete button didn't — switched to `mutateAsync`). The **second** review
  (of that follow-up commit `41473fa`) found 2 of those 4 fixes had zero
  test coverage for their new branches — and writing the `deps.py` test
  is what revealed that fix wasn't real: PyJWT's own `decode()` already
  raises `InvalidSubjectError` (a `PyJWTError`, already caught) for any
  non-string `sub` before `get_current_user` ever reaches
  `uuid.UUID(user_id)`, so the `AttributeError` branch was dead code for
  an already-impossible scenario — reverted per this file's own "don't
  add handling for what can't happen" convention (`ca20db8`), while the
  `showUndoToast` sync-throw test was confirmed real (temporarily
  reverted the fix, watched the new test fail with an uncaught exception,
  restored it). Final state: 323 backend tests, 241 frontend tests, all
  green, CI green on every push. A follow-up pass over every non-backend/
  non-frontend file (docs, YAML, `.gitignore`/`.gitattributes`, images)
  found the rest already accurate and consistent (`.env.example` matches
  `config.py` field-for-field; `docs/final_report.md`/
  `docs/demo_video_script.md` are correctly, deliberately frozen
  snapshots with no live-fact errors) except one: `stu-dent-architecture.png`
  depicted the deleted VM-deploy path and stale test counts matching
  neither current reality nor even `final_report.md`'s own frozen
  snapshot, and was referenced nowhere. A Mermaid-diagram replacement was
  drafted but not approved — the user wants to keep an actual PNG,
  regenerated through their own image generator rather than authored by
  Claude — so the original file was kept and given a real reference (a
  README embed, fixing the "referenced nowhere" half of the finding) while
  a precise edit-prompt describing exactly what to fix in the image
  (remove the deleted VM-deploy box/legend/arrow, add the new
  dependency-audit CI job, update the stale test counts) was handed to the
  user to run through their generator themselves.
