# Roadmap

Mad Light’s product arc is **local meeting facilitation cues**, not a cloud note-taker and not a Zoom competitor.

**Light** means a signal / bulb (the LED), not a “lite” edition.

This file is direction, not a schedule. **The heat dial (overlap-first) is what this repo ships** (see [SPEC.md](SPEC.md)). Later versions stay out of the tree until they earn their own slice.

License: **MIT** (see [LICENSE](LICENSE)). Docs are open-source ready; whether or when the repo goes public is undecided.

## Who it’s for

North-star uses. They explain *why* the dial exists. They do **not** expand v0.

**Accessibility / neurodiversity-minded.** Some people want a simple **non-verbal ambient cue** when conversation heat rises, or when an ask is not landing — something you can glance at without parsing a transcript or a dashboard. Mad Light is **not a medical device**. It does not diagnose, treat, or detect a condition. No clinical claims.

**Parth in live 2–5 person video calls.** Private, local, real-time glanceable cue when the room is escalating so he can soften or steer. Not emotion theater.

**Executive / cryptic meetings (personal use case).** In rooms where the ask is restated and still does not land, the holder wants a cue to **reframe**. That **clarity / facilitator** behavior is **v2+**. Today the LED shows **talk-over heat** (green / amber / red), not “point landed?”.

## How you get it

1. **Runnable local app** — this repo, Omarchy / Linux first. `madlight` on the default-sink monitor. One recording-indicator **dot**.
2. **Spec + agent recipe** — [SPEC.md](SPEC.md) is the contract. Optionally drop [`.cursor/skills/mad-light/SKILL.md`](.cursor/skills/mad-light/SKILL.md) into a coding agent so a PM can say “build Mad Light to this spec” and get a faithful local dial whose yellow/red mean **talk-over**, **not** the later facilitator features.

## Now — Atmosphere Dial (overlap-first)

A single always-on-top **heat circle**: **green / amber / red** (calm / rising / hot) from **talk-over / interrupted turn-taking** on the monitor-sink mix (classical DSP: dual F0 + envelope tightness). RMS / slope are secondary room energy only. Tray icon mirrors the colors. Kill/off is on the tray / circle.

- Offline. No cloud API in the audio path.
- Default: **do not write audio or transcripts to disk.**
- Not emotion labels, not face reading, not ASR, not a dashboard.
- Kill switch stops capture.
- Local thumbs (`feedback.jsonl`) can **recompute overlap sensitivity** (`madlight calibrate --from-feedback`).

That is the whole current product. Install and run it.

Offline **`madlight calibrate`** (see [CALIBRATE.md](CALIBRATE.md)) scores labeled clips against these same thresholds and can propose `--overlap-rising` / `--overlap-hot` flags. Grid search or thumbs fit — not neural training, not cloud.

## v1 — Stacking / interrupt signals (landed as the heat driver)

Same machine, same “what you already hear” capture. **Talk-over is now the primary heat signal** (not a second pip):

- Talk-over / pile-on (dual-F0 + envelope stacking, not speaker ID).
- Interrupt-ish short-gap tightening vs a peaky monologue.
- Yellow/red = sustained overlap / escalation, not one emphatic loud word.

Still no Whisper, no cloud, no “who said what.” A second stacking pip / blink remains optional later. If a cue needs words, it is not this slice.

## v2 — Clarity / facilitator arc (“point landed?” / reframe)

This is the **clarity and facilitator** slice — still a coach, **not** a meeting note-taker.

Cues for **whether the room is still with the point**, and whether someone should **restate, check understanding, or rephrase** (the “ten commandments” style framework: *restate the point; check that it landed; rephrase if it did not*).

Fits the cryptic-meeting use case: the ask was repeated; it still did not land; **reframe**.

- No default transcript on disk.
- No auto-summary emailed to the calendar.
- “Point landed?” is a **cue**, not a claim that we read minds or faces.

The Point (the overlay) is ancestor inspiration only. v2 should not copy that YouTube/manual engine.

v0/v1 energy features may feed v2. **Do not grow the v0 LED into this.**

## v3 — Dual local guides (opt-in both sides)

Two people, two local instances, **both opt in**, exchanging **peer signals** (atmosphere, stacking, “reframe?”) — not a recording of the other person, not a stealth coach.

Hard rules to keep:

- Explicit consent on each side.
- Local-first; if anything leaves the machine, it is a later, named choice — not a silent default.
- Either party can kill their guide without affecting the other’s Off switch.

**Same era (~v3), optional, local only:** thumbs up / down on a recent cue so Mad Light can **nudge its own thresholds / sensitivity on-device** (this headset is quieter; that room is always “hot”). Ratings and the resulting numbers stay on the machine. **Not cloud retraining**, not a model upload, not a dataset leaving the box.

A **lite** slice of this (card + / −, `prefs.json`, `feedback.jsonl`, on-device nudge, and `madlight calibrate --from-feedback`) shipped on the floating card. It is still local-only and is not the dual-guide product.

## v4 — Skills / hooks (others may adopt)

A small, boring interface so **Zoom, Teams, a browser app, or a plugin** *can* show the same cues or embed the framework.

Honest limits:

- Publishing hooks does **not** mean Zoom or Teams will adopt them.
- Success is **copyable**: if this is public, awareness and credit; a product owner **may** bake the framework or the dial into their own client.
- Keep the core license permissive (MIT) so “bake in” is legally easy. Ask for attribution; do not expect a vendor program.

The in-repo [agent skill](.cursor/skills/mad-light/SKILL.md) is for **rebuilding v0 from SPEC**, not a Zoom integration.

## Non-goals (unless a later version says otherwise)

Cloud inference, mandatory ASR, speaker identification as a product, auto-update, signed store installers, writing the meeting to disk by default, claiming platform adoption we do not have, medical or diagnostic claims.

Windows WASAPI loopback is a port of **v0 capture**, not a new product version. It can land whenever someone needs it; it does not unlock v1.
