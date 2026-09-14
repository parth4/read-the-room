# Mad Light — spec

Hand this file to a coding agent: *build Mad Light to this spec.*

**Product:** Mad Light. **MAD** = Meeting Atmosphere Dial. **Light** = a signal / bulb, not a “lite” edition.

**Who it’s for:** Parth in live **2–5 person video calls** — a private, local, real-time glanceable cue when the room is escalating (talk-over) so he can soften or steer. Also useful as a non-verbal ambient cue (accessibility / neurodiversity-minded). **Not a medical device.** No diagnosis.

**Not:** emotion theater, manager dashboards, offline-only analysis, mind-reading, face analysis.

A reference implementation lives in this repo (`madlight`). A faithful rebuild may use different libraries if behavior matches.

The **clarity / facilitator** arc (“point landed?”, reframe, commandments, dual guides, vendor hooks) is **[ROADMAP.md](ROADMAP.md)** v2+ — do not implement those here.

## What to ship

While a meeting plays on the machine (Zoom / Teams / browser), show **one** always-on-top **card** with a recording-indicator-style **colored circle** (green / amber / red / idle grey), headphone listen/pause, and one energy strip.

| Color | Meaning (talk-over, not loudness, not emotion) |
| --- | --- |
| Green | calm — no sustained talk-over |
| Amber | rising — sustained overlap / interrupted turns |
| Red | hot — heavier, longer talk-over |
| Grey | idle (near-silence, still listening) or paused |

- Faces (🙂 / 😬 / 😡) are **glanceable state icons**, not emotion AI. Copy must say heat is talk-over / room-escalation cues.
- Tray icon may **mirror the same colors**. Kill / off is on the **tray** (click the circle; Space / Escape).
- Off **stops capture immediately**. Keep headphone listen/pause + AA circle behavior.

## Hard UI constraints

- Compact floating card, not a dashboard. Center circle on the order of **44px**. Always on top. Draggable. Window title `Mad Light`.
- Colors tunable; names stay green / amber / red / grey-off.
- Optional tiny honesty caption (`talk-over · not emotion`) is fine. Do not put live “CALM / HOT” status text on the circle.

## Privacy (non-negotiable)

- Completely **offline**. No cloud in the audio path.
- **Default: do not write audio or transcripts to disk.** No recorder, no WAV, no ASR. Thumbs write numbers only (`feedback.jsonl`).
- Capture the **monitor of the default sink** (what the user already hears). Headphones must work if they are the default sink.
- **Never silently fall back to the microphone.** If there is no monitor, exit with instructions.
- `--allow-mic` may exist as an explicit footgun; it must not be the default.

## Capture

Primary: **Omarchy / Arch-like**, PipeWire or PulseAudio. Also **Windows WASAPI** loopback via `soundcard`.

1. Resolve default sink (`pactl get-default-sink` or equivalent).
2. Open that sink’s **`.monitor` / loopback**.
3. Backends: `soundcard` loopback, then `parec`, then `pw-record`.

`--list-sources` lists **monitors only** and marks the default.

`--demo` feeds synthetic **two-voice overlap** (no device) so the LED can be tested without a meeting: quiet → rising → hot.

## Heat classifier (overlap-first)

Talk-over on the loopback mix. Not emotion, not speech content, not faces, not speaker ID.

- Block RMS (stereo downmix), ~**50 ms** blocks, ~**16 kHz**.
- **Primary:** lightweight overlap score over ~**0.5–2 s** (default 1 s):
  - Independent F0 peaks in 80–400 Hz (two talkers; reject harmonics).
  - Envelope fill / crest / short-gap tightness (interrupted turn-taking).
  - Gate out flat held tones / music (near-zero CV + crest ≈ 1).
- **Secondary:** RMS / slope as room energy. May slightly lower the overlap cut once overlap is already present. **Must not promote** a loud monologue or one emphatic word.
- Map to calm / rising / hot with **hysteresis + dwell** so the LED does not flicker. One rank at a time (calm → rising → hot).
- Real-time on desktop (no multi-second lag; no pyannote/torch unless a tiny optional path is clearly needed).

Suggested starting thresholds:

| Name | Default |
| --- | --- |
| `overlap_rising` | 0.48 |
| `overlap_hot` | 0.86 |
| `overlap_drop` | 0.08 |
| `rise_dwell_seconds` | 0.70 |
| `hot_dwell_seconds` | 0.40 |
| `rising_rms` | 0.08 (secondary) |
| `hot_rms` | 0.22 (secondary) |
| `rising_slope` | 0.14 / s (secondary) |
| `silence_rms` | 0.008 |

Unit-test with **synthetic clips** (no microphone): loud monologue stays calm; overlapping voices → rising/hot with dwell; one emphatic word stays calm.

## Thumbs → calibration

`feedback.jsonl` schema is in `madlight/feedback.py` and [CALIBRATE.md](CALIBRATE.md).

- Tune + / − logs a labeled moment (overlap + envelope + level).
- After repeated downs, nudge overlap sensitivity on-device.
- `madlight calibrate --from-feedback --write-prefs` (and gear **Apply Tune ratings**) **fit overlap cuts from recent thumbs** — prefer his VC-mix domain over universal defaults.

## Stack (KISS)

- Python 3.11+
- numpy for RMS / FFT overlap
- Simplest reliable Linux monitor + Windows WASAPI loopback
- pystray + optional Tk for the card
- Entry: `madlight` and/or `python -m madlight`
- `pytest` for overlap + dwell + prefs/feedback; `--demo --text` for a wall-clock calm → rising → hot loop

Repo slug may stay `mad-lite`. Package / CLI name: **madlight**.

## Out of scope

Whisper / ASR, speaker ID, emotion / face models, Point faces, cloud APIs, auto-update, signed installers, writing meeting audio to disk, medical claims, “point landed?” / reframe / ten-commandments coach UI.

## Done when

1. Synthetic/fixture: loud monologue stays calm; overlapping voices → rising/hot with dwell.
2. One emphatic word does not flip yellow.
3. Feedback can adjust overlap sensitivity in a documented way.
4. Real-time path still suitable for live calls (no multi-second lag).
5. README explains who it’s for and that the signal is talk-over, not emotion AI.
6. Headphone listen/pause + AA circle still work. No network in the audio path.
