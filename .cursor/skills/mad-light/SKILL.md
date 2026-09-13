---
name: mad-light
description: Build or verify Mad Light v0 from the repo SPEC — local heat LED only. Use when a PM or agent is asked to implement Meeting Atmosphere Dial, a recording-indicator heat dot, or “build Mad Light to this spec.”
---

# Build Mad Light (v0)

Read and obey **[SPEC.md](../../../SPEC.md)** at the repo root. That file is the contract.

## Product

- Name: **Mad Light**. MAD = Meeting Atmosphere Dial. Light = signal/bulb, not “lite edition.”
- Ship a **local** default-sink **monitor** capture → RMS/slope → **one** always-on-top **green / amber / red** recording-pip **dot**.
- Tray mirrors colors. Off on the tray stops capture. No mic fallback. No audio/transcripts on disk. No cloud.

## Do not build (even if the user mentions them)

These live on **[ROADMAP.md](../../../ROADMAP.md)** as the **clarity / facilitator arc**, not v0:

- Talk-over / stacking (v1)
- “Point landed?” / reframe / ten-commandments coach (v2+)
- Dual opt-in guides (v3)
- Zoom/Teams hooks as if a vendor will adopt them (v4)

Do not copy [The Point](https://github.com/parth4/point-overlay) YouTube/manual engine.

## Who it’s for (do not overclaim)

- Accessibility / neurodiversity-minded: a **non-verbal ambient cue**. **Not a medical device.** No diagnosis.
- Executive / cryptic meetings: later, signal to **reframe** when an ask still does not land. v0 is heat only.

## Checks

- Overlay is a **tiny circle** (≲ 28px window), not a labeled pill or dashboard.
- Classifier unit tests use synthetic energy (no mic).
- `--demo` shows calm → rising → hot without a meeting.
- README / SPEC still say v0 is the heat dial only.
