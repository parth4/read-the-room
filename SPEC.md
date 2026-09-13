# Mad Light — v0 spec

Hand this file to a coding agent: *build Mad Light to this spec.*

**Product:** Mad Light. **MAD** = Meeting Atmosphere Dial. **Light** = a signal / bulb, not a “lite” edition.

**This spec is v0 only.** Do not implement [ROADMAP.md](ROADMAP.md) v1+ (stacking, “point landed?”, commandments, dual guides, vendor hooks). Those are the clarity / facilitator *arc*, not this build.

A reference implementation lives in this repo (`madlight`). A faithful rebuild may use different libraries if behavior matches.

## Who it’s for (north star)

1. **Accessibility / neurodiversity-minded use** — a simple **non-verbal ambient cue** when conversation heat rises, or when an ask is not landing. **Not a medical device.** No diagnosis, no ADHD/autism claims, no “detects distress.”
2. **Executive / cryptic meetings** (personal use case) — when an ask is restated and still does not land, the later product should help the holder **reframe**. v0 only shows **atmosphere heat**. Reframe / “point landed?” is **v2+**.

v0 is a heat LED. It does not know whether a point landed.

## What to ship (v0)

While a meeting plays on the machine (Zoom / Teams / browser), show **one** always-on-top **recording-indicator-style colored dot** (tiny circle — hardware LED / Zoom rec pip).

| Color | Meaning (energy only) |
| --- | --- |
| Green | calm — quiet / steady low energy |
| Amber | rising — mid energy or energy climbing |
| Red | hot — high RMS |
| Grey | off — not listening |

- **Not** a labeled pill, **not** a dashboard, **not** status text on the overlay.
- Tray icon may **mirror the same colors**. Kill / off is on the **tray** (right-click the dot if there is no tray).
- Off **stops capture immediately**.

## Hard UI constraints

- One circle. Diameter on the order of **16px** (window ≲ 28px). If it looks like a toolbar or a “CALM / OFF” chip, it is wrong.
- Always on top. Draggable. Window title `Mad Light` (for compositor rules).
- Colors tunable; names stay green / amber / red / grey-off.

## Privacy (non-negotiable)

- Completely **offline**. No cloud in the audio path.
- **Default: do not write audio or transcripts to disk.** No recorder, no WAV, no ASR.
- Capture the **monitor of the default sink** (what the user already hears). Headphones must work if they are the default sink.
- **Never silently fall back to the microphone.** If there is no monitor, exit with instructions.
- `--allow-mic` may exist as an explicit footgun; it must not be the default.

## Capture (Linux first)

Primary target: **Omarchy / Arch-like**, PipeWire or PulseAudio.

1. Resolve default sink (`pactl get-default-sink` or equivalent).
2. Open that sink’s **`.monitor` / loopback**.
3. Backends that work in practice: `soundcard` loopback, then `parec`, then `pw-record`.
4. Do not block v0 on Windows. WASAPI loopback may be noted, not required.

`--list-sources` lists **monitors only** and marks the default.

`--demo` feeds synthetic energy (no device) so the LED can be tested without a meeting.

## Heat classifier

Energy only. Not emotion, not speech content, not faces.

- Block RMS (stereo downmix), ~**50 ms** blocks, ~**16 kHz**.
- Smooth over a short window (~**0.6 s** of recent RMS).
- Slope: newer window minus older window, per second (~**0.6 s** halves).
- Map to calm / rising / hot with **hysteresis** so the LED does not flicker.

Suggested starting thresholds (linear amplitude 0..1; tune):

| Name | Default |
| --- | --- |
| `rising_rms` | 0.045 |
| `hot_rms` | 0.11 |
| `rising_slope` | 0.035 / s |
| `drop_margin` | 0.015 |
| `silence_rms` | 0.008 |

Quiet + steep slope → rising. Near-silence slope noise must stay calm. Unit-test with **synthetic RMS sequences** (no microphone).

## Stack (KISS)

- Python 3.11+
- numpy for RMS / slope
- Simplest reliable Linux monitor capture
- pystray + optional Tk for the dot
- Entry: `madlight` and/or `python -m madlight`
- `pytest` for the classifier; `--demo --text` for a wall-clock calm → rising → hot loop

Repo slug may stay `mad-lite`. Package / CLI name: **madlight**.

## Out of scope (v0)

Whisper / ASR, speaker ID, talk-over, Point faces, cloud APIs, auto-update, signed installers, writing meeting audio to disk, medical claims, “point landed?” / reframe / ten-commandments coach UI.

## Done when

Fresh clone → install → run → monitor of the default sink → the **dot** goes green on quiet playback and amber/red on loud. Tray (or right-click) Off stops listening. No network in the audio path.
