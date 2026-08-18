# Stu-Dent — Gallery Demo Video Script (short cut)

This is a **separate, short recording** for the Project Gallery zip's
optional `demo.mp4` — not a trim of `demo_video_script.md` (the ~12-14 min
course-submission video). The gallery's `check_submission.sh` **rejects**
anything outside these limits automatically, so hit them exactly, don't
approximate:

- **Length: 20-90 seconds** (aim for ~65-75s — enough room to breathe
  without risking the upper bound)
- **Resolution: exactly 1920×1080** — set this as the actual screen/OBS
  capture resolution before recording, don't resize/upscale afterward
- **Format: MP4**
- **Silent** — no narration/audio track (mute the mic, or record silent and
  skip adding audio in the editor)

No talking, so lean on quick, confident mouse movement and a beat of pause
after each key state change (e.g. the conflict modal appearing) so a viewer
skimming without sound can follow what happened. Use the seeded demo
accounts (`docker compose exec api python -m app.seed_demo`, password
`DemoPass123!` for all) — nothing should need to be typed slowly on camera.

---

## Shot list (~70s total)

1. **(0-8s) Calendar view.** Log in as `student1@stu-dent.demo`, land on
   `/appointments`, switch to the week or month calendar view. A couple of
   seconds on a populated calendar — this is the single most visual proof
   the system is a real, working scheduler, not a mockup.

2. **(8-30s) The headline feature: conflict → waitlist, live.** Click an
   already-booked slot's time range to open "New Appointment," fill it in
   so it collides with an existing booking (reuse a patient/resource you
   can see is already busy on the calendar), submit, and let the real
   `ConflictResolutionModal` appear — pause ~2s so it's readable ("This
   request isn't available," naming the exact busy resource). Click "Join
   waitlist." Cut to `/waitlist` showing the new entry with its conflict
   cause badge.

3. **(30-45s) Auto-promotion.** Either narrate this with an on-screen text
   card ("conflict clears → auto-booked, no manual step") over a quick
   before/after of the waitlist entry flipping to "promoted" once the
   blocking appointment is cancelled, or — if pre-staged — show the
   cancel action and the waitlist entry updating live via the WebSocket
   push, no page refresh. Keep this beat tight; it's the hardest one to
   read silently, so a short on-screen caption is worth it here even
   though the rest of the video has none.

4. **(45-60s) Local AI, kept on a leash.** Open the natural-language
   scheduling box, type something like "book Dana with Dr. Cohen next
   Tuesday afternoon," and show the form auto-filling with resolved
   real names/date — then cut to `/reports`, showing an AI-narrated
   report card.

5. **(60-70s) The rest of the clinic loop.** A fast 2-3s glance each at:
   the forum feed, a messaging thread, and the admin rooms/equipment page
   — enough to signal "this is a whole system," not a lingering tour.

---

## Notes

- If Ollama isn't pulled/warmed up before recording, step 4's AI segments
  fall back to their plain warning/raw-data path — that's honest to show,
  but if you want genuine model output, `docker compose exec ollama ollama
  pull llama3.2` first and give it one warm-up query before recording so
  the on-camera response isn't slow.
- After recording, run
  `MSYS_NO_PATHCONV=1 bash "submission instructions/check_submission.sh" gallery/308560150.zip`
  (with `demo.mp4` added into the zip alongside `metadata.json` and
  `poster.pdf`) to confirm length/resolution pass before submitting.
