---
name: mad-light
description: Build or verify Mad Light from the repo SPEC — local talk-over heat LED. Use when a PM or agent is asked to implement Meeting Atmosphere Dial, a recording-indicator heat dot, or “build Mad Light to this spec.”
---

# Build Mad Light

Read and obey **[SPEC.md](../../../SPEC.md)** at the repo root. That file is the contract.

## Product

- Name: **Mad Light**. MAD = Meeting Atmosphere Dial. Light = signal/bulb, not “lite edition.”
- For **Parth in live 2–5 person video calls**: private, local, real-time glanceable cue when the room is escalating (talk-over) so he can soften/steer.
- Ship a **local** default-sink **monitor** capture → **overlap-first heat** (dual F0 + envelope tightness; RMS/slope secondary) → always-on-top **green / amber / red** circle + headphone listen/pause.
- Tray mirrors colors. Off stops capture. No mic fallback. No audio/transcripts on disk. No cloud.
- Yellow/red = **sustained talk-over**, not loudness and not emotion AI.

## Do not build (even if the user mentions them)

These live on **[ROADMAP.md](../../../ROADMAP.md)** as the **clarity / facilitator arc**:

- “Point landed?” / reframe / ten-commandments coach (v2+)
- Dual opt-in guides (v3)
- Zoom/Teams hooks as if a vendor will adopt them (v4)
- Heavy ML (pyannote/torch) unless a tiny optional path is clearly needed

Do not copy [The Point](https://github.com/parth4/point-overlay) YouTube/manual engine.

## Who it’s for (do not overclaim)

- Live 2–5 person VC: glanceable talk-over / escalation cue. **Not** emotion theater, not a manager dashboard.
- Accessibility / neurodiversity-minded: a **non-verbal ambient cue**. **Not a medical device.** No diagnosis.
- Executive / cryptic meetings: later, signal to **reframe** when an ask still does not land. Today is heat only.

## Checks

- Headphone listen/pause + AA circle still work.
- Classifier unit tests use synthetic audio (no mic): loud monologue stays calm; overlap → rising/hot with dwell; one emphatic word stays calm.
- `--demo` shows calm → rising → hot without a meeting (overlap, not a loudness ramp).
- Feedback schema is documented; `--from-feedback` can adjust overlap sensitivity.
- README / help say heat is **talk-over / room-escalation cues**, not emotion AI.
