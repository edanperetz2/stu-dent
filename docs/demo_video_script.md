# Stu-Dent — Demonstration Video Script

Covers everything proposal §6 requires: "main workflows and test
execution." Rough total runtime ~10-12 minutes; trim/cut segments as
needed. Uses the seeded demo accounts (`docker compose exec api python -m
app.seed_demo`, password `DemoPass123!` for all) so nothing needs to be
created live on camera except where noted.

Before recording: `docker compose up --build`, then seed demo data, then
optionally `docker compose exec ollama ollama pull llama3.2` if you want
the AI segments to show genuine model output instead of the graceful
fallback (either is honest to show — the fallback demonstrates the
degrade-gracefully design decision, which is itself worth narrating).

---

## 1. Intro (~30s)

Talking head or voiceover over the README/repo view. Say: the real-world
problem (dental students coordinating patients over WhatsApp/spreadsheets,
causing conflicts and missed appointments), and the one-line pitch —
Stu-Dent centralizes scheduling, resources, communication, and adds a
local AI assistant, fully Dockerized with no paid services.

## 2. One-command local run (~30s)

Terminal: `docker compose up --build` against a clean checkout (or just
narrate over an already-running stack to save time). Show
`http://localhost:8000/health` and `http://localhost:5173` both up.
Narrate: one documented command, no local Python/Node install needed.

## 3. Core scheduling workflow (~3 min) — the main event

1. Log in as `student1@stu-dent.demo`. Show the Patients list (Demo
   Patient 1, Demo Patient 4).
2. Appointments page → New Appointment. Demonstrate the **NL scheduling
   interpreter**: type something like "book Demo Patient 1 tomorrow
   afternoon, routine checkup" into "Describe it in your own words",
   click Interpret, show the form auto-filling the patient/date/notes
   fields. Narrate: the model only extracts names/phrases — the actual
   patient ID and date math are resolved deterministically in code, never
   trusted verbatim from the model.
3. Submit the appointment, show it land in the list with a status badge.
4. **Conflict prevention demo** (important, proposal §4.3 headline
   feature): try to book a second appointment for the same attending/room
   at an overlapping time — show the 409 rejection. This is the
   database-level exclusion-constraint guarantee, not just an
   application check.
5. Log in as `attending1@stu-dent.demo` in a second window/incognito tab,
   show the awaiting-confirmation appointment, click Approve, show the
   status flip to Confirmed.
6. Back as the patient (`patient1@stu-dent.demo`), show them seeing the
   same confirmed appointment.

## 4. Waitlist + reminders + notifications (~1 min)

Show the Waitlist page (seeded entries). Show the Notifications page —
point out the unread-count badge in the nav, the read/unread visual
distinction. Mention the background worker polls for reminders and
expires stale unconfirmed appointments, and optionally show MailHog
(`http://localhost:8025`) with a seeded reminder email sitting in the
inbox.

## 5. Communication: forum + direct messages (~1 min)

Forum page: show the seeded posts, a comment, a vote (click to change
your own vote, show the score update). Messages page: show the seeded
patient↔student thread, send one live message, show it appear
instantly (real-time, no refresh) if demoing in two windows side by side.

## 6. Admin management (~30s)

Log in as `admin@stu-dent.demo`. Show Users (role change / deactivate),
Rooms/Equipment CRUD.

## 7. Local AI report assistant (~1.5 min)

Reports page (as a student or attending). Click "Generate report now",
show the weekly/monthly reports appear with narrated content. Type an
ad-hoc question in "Ask a question" — e.g. "which room is underused this
month?" — show a real answer. Then type something off-topic — e.g. "what
should I have for lunch?" — show the plain "I can only answer questions
about..." response. Narrate: this is deliberate — the model only ever
classifies into a small fixed set of supported question types and
extracts a date range; it never sees the database or writes a query, so
an unsupported question gets an honest "I can't answer that" instead of
a hallucinated guess.

## 8. Test execution (~1.5 min) — required by proposal §6

Terminal, run live:
```
docker compose exec api pytest -v
```
Let it scroll briefly, then cut to the summary line (all passed — the
exact count drifts as tests are added, so read whatever's on screen
rather than a number written here). Then:
```
docker compose exec frontend npm run test
docker compose exec frontend npm run build
```
Narrate the numbers on screen (backend and frontend test counts) and mention the
testing philosophy briefly: real Postgres exclusion constraints under
test, Ollama calls mocked for determinism, a few tests that need genuine
cross-connection commit visibility bypass the usual rollback-per-test
fixture on purpose.

## 9. CI/CD pipeline (~30s)

Show the GitHub Actions tab — the green run with all four jobs (lint,
backend-tests, frontend-tests, docker-build). Mention briefly: catches
regressions on every push, including a Dockerfile-build check for both
dev and production images.

## 10. Deployment status (~1 min)

Show `docker-compose.prod.yml` briefly in an editor. Explain: this is a
hardened production stack (no dev bind-mounts, built frontend served by
nginx instead of the Vite dev server) — rehearsed successfully as a full
local dry run reusing the same database, but not yet deployed to the
real course-supplied VM, which wasn't available yet at the time of
recording. If it *has* been deployed by recording time, show the real
public URL instead of the local rehearsal.

## 11. Wrap-up (~30s)

Quick recap slide/voiceover: 7 phases built plus ongoing post-submission
feature work, a large automated test suite (see the counts from section
8), real
AI trust-boundary design (interpret-only, never decide), fully
Dockerized, CI green, deployment-ready. Mention `docs/final_report.md`
for the full written writeup.
