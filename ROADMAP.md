# Roadmap

Mad Lite’s product arc is **local meeting facilitation cues**, not a cloud note-taker and not a Zoom competitor.

This file is direction, not a schedule. **v0 is what this repo ships.** Later versions stay out of the v0 tree until they earn their own slice.

License: **MIT** (see [LICENSE](LICENSE)). The repo is written as if it will be public: fork it, credit it, bake pieces in.

## v0 — Atmosphere Dial (now)

A tiny local heat pill: **calm / rising / hot** from crude monitor-sink audio (RMS + short-term energy slope).

- Offline. No cloud API in the audio path.
- Default: **do not write audio or transcripts to disk.**
- Not emotion labels, not faces, not ASR.
- Kill switch stops capture.

That is the whole v0 product. Install and run it; do not wait for v1.

## v1 — Stacking / interrupt signals (still local)

Same machine, same “what you already hear” capture. Add **more audio features**, still not a transcript:

- Talk-over / pile-on (energy stacking, not speaker ID).
- Interrupt-ish spikes vs a steady floor.
- Maybe a second pill or a small badge: *stacking* vs *one voice*.

Still no Whisper, no cloud, no “who said what.” If a cue needs words, it is not v1.

## v2 — “Point landed?” / reframe-needed (coach, not notes)

Cues for **whether the room is still with the point**, and whether someone should **restate, check understanding, or rephrase**.

This is a **facilitator / coach**, not a meeting note-taker:

- No default transcript on disk.
- No auto-summary emailed to the calendar.
- A tiny communication framework — “ten commandments” style, short enough to memorize — something like: *restate the point; check that it landed; rephrase if it did not.*

The Point (the overlay) is ancestor inspiration only. v2 should not copy that YouTube/manual engine. “Point landed?” will be a **cue**, not a claim that we read minds or faces.

v0/v1 energy features may feed v2. **Do not grow the v0 heat dial into this.**

## v3 — Dual local guides (opt-in both sides)

Two people, two local instances, **both opt in**, exchanging **peer signals** (atmosphere, stacking, “reframe?”) — not a recording of the other person, not a stealth coach.

Hard rules to keep:

- Explicit consent on each side.
- Local-first; if anything leaves the machine, it is a later, named choice — not a silent default.
- Either party can kill their guide without affecting the other’s Off switch.

## v4 — Skills / hooks (others may adopt)

A small, boring interface so **Zoom, Teams, a browser app, or a plugin** *can* show the same cues or embed the framework.

Honest limits:

- Publishing hooks does **not** mean Zoom or Teams will adopt them.
- Success is **copyable**: open source for awareness and credit; a product owner **may** bake the framework or the dial into their own client.
- Keep the core license permissive (MIT) so “bake in” is legally easy. Ask for attribution; do not expect a vendor program.

## Non-goals (unless a later version says otherwise)

Cloud inference, mandatory ASR, speaker identification as a product, auto-update, signed store installers, writing the meeting to disk by default, claiming platform adoption we do not have.

Windows WASAPI loopback is a port of **v0 capture**, not a new product version. It can land whenever someone needs it; it does not unlock v1.
