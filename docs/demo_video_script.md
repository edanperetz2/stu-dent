# Stu-Dent — Demonstration Video Script

Covers everything proposal §6 requires: "main workflows and test
execution." Rough total runtime ~12-14 minutes; trim/cut segments as
needed. Uses the seeded demo accounts (`docker compose exec api python -m
app.seed_demo`, password `DemoPass123!` for all) so nothing needs to be
created live on camera except where noted.

Before recording: `docker compose up --build`, then seed demo data, then
optionally `docker compose exec ollama ollama pull llama3.2` if you want
the AI segments to show genuine model output instead of the graceful
fallback (either is honest to show — the fallback demonstrates the
degrade-gracefully design decision, which is itself worth narrating).

Updated after the original submission to reflect everything built in the
post-submission arc: dark mode, forgot-password, the rebuilt booking
modal, the appointments calendar, and the waitlist redesign. The VM
deployment plan (section 10, previously) was dropped entirely once the
course confirmed no VM would be provided — that segment is gone rather
than left pointing at a deleted file.

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

## 3. Login extras: dark mode + forgot password (~1 min)

1. On the login page, point out `autoComplete`/`type="email"` letting a
   password manager fill the form, and that there's no Role dropdown —
   the backend validates the real role, so a picker could only ever cause
   a wrong-choice failure.
2. Click "Forgot password?", submit an email, then show the email
   actually arriving in MailHog (`http://localhost:8025`) — narrate that
   the response is identical whether or not the email exists (enumeration
   resistance) and that it's rate-limited per-email and per-IP. Follow
   the link, set a new password, log in with it.
3. Log in as `student1@stu-dent.demo`, then click the sun/moon toggle in
   the header to show real dark mode — not just a CSS media query, a full
   Mantine theme with a brand color derived from the logo, scheme-aware
   hover states, and status badges that switch to a saturated/AA-verified
   palette instead of staying a pale light-mode pill.

## 4. Core scheduling workflow (~3.5 min) — the main event

1. Still as `student1@stu-dent.demo`. Show the Patients list (Demo
   Patient 1, Demo Patient 4).
2. Appointments page → New Appointment. Point out the rebuilt modal:
   fields grouped into Who / When / Where, duration shortcut chips
   (30/45/60/Custom) instead of a second manual time picker, and the AI
   "describe it" box tucked behind a "Describe instead" toggle rather
   than sitting above the form. Demonstrate the **NL scheduling
   interpreter**: toggle it on, type something like "book Demo Patient 1
   tomorrow afternoon, routine checkup", click Interpret, show the form
   auto-filling the patient/date/notes fields. Narrate: the model only
   extracts names/phrases — the actual patient ID and date math are
   resolved deterministically in code, never trusted verbatim from the
   model.
3. Submit the appointment, show it land in the list with a status badge.
4. **Conflict prevention demo** (important, proposal §4.3 headline
   feature): try to book a second appointment for the same attending/room
   at an overlapping time. Show the `ConflictResolutionModal` that opens
   instead of a bare error — it names exactly which resource is busy and
   offers "adjust and retry" or "join the waitlist with this exact
   request." Pick join-waitlist. Narrate: this is backed by a real
   Postgres exclusion constraint, not just an application-level check —
   the modal is just an honest explanation of that guarantee instead of
   a raw 409.
5. Switch to the Calendar sub-view (List/Calendar toggle). Show
   month/week/day views bounded to clinic hours (08:00-21:30, not a
   scrollable 24-hour grid), and switch the lens from Personal to
   Resources to show every room/equipment booking color-coded, with
   filter chips to show/hide individual resources.
6. Log in as `attending1@stu-dent.demo` in a second window/incognito tab,
   show the awaiting-confirmation appointment, click Approve, show the
   status flip to Confirmed.
7. Back as the patient (`patient1@stu-dent.demo`), show them seeing the
   same confirmed appointment.

## 5. Waitlist + reminders + notifications (~1.5 min)

Show the Waitlist page — narrate that this isn't a manually-filled form,
it's a log of real booking attempts that hit a genuine conflict: each
entry shows a cause badge naming exactly what was busy (room, attending,
patient, etc.), and resolves automatically into a real appointment the
moment that resource frees up, first-come-first-served. If viewing as the
patient whose entry was caused by their own student being busy, point out
the cause is shown generically ("patient busy") rather than revealing
which other patient's care the student was occupied with — a deliberate
confidentiality redaction that only applies to the patient's own view.
Show the Notifications page — point out the unread-count badge in the
nav, the read/unread visual distinction. Mention the background worker
polls for reminders and expires stale unconfirmed appointments, and
optionally show MailHog with a seeded reminder email sitting in the
inbox.

## 6. Communication: forum + direct messages (~1 min)

Forum page: show the seeded posts, a comment, a vote (click to change
your own vote, show the score update). Messages page: show the seeded
patient↔student thread, send one live message, show it appear
instantly (real-time, no refresh) if demoing in two windows side by side.

## 7. Admin management (~30s)

Log in as `admin@stu-dent.demo`. Show Users (role change / deactivate),
Rooms/Equipment CRUD.

## 8. Local AI report assistant (~1.5 min)

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

## 9. Test execution (~1.5 min) — required by proposal §6

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

## 10. CI/CD pipeline (~30s)

Show the GitHub Actions tab — the green run with all four jobs (lint,
backend-tests, frontend-tests, docker-build). Mention briefly: catches
regressions on every push, including a Dockerfile-build check for both
the API and frontend images.

## 11. Wrap-up (~30s)

Quick recap slide/voiceover: 7 phases built plus extensive ongoing
post-submission feature work (real dark mode, forgot-password, a
redesigned booking flow and waitlist, a frontend accessibility pass), a
large automated test suite (see the counts from section 9), real AI
trust-boundary design (interpret-only, never decide), fully Dockerized,
CI green. Mention `docs/final_report.md` for the full written writeup —
note that it's frozen as of course submission and predates most of the
post-submission work shown in this video.
