# Mad Light

**MAD = Meeting Atmosphere Dial.** **Light** = a signal / bulb — not “lite” as in a cut-down edition.

While a meeting plays on this machine (Zoom, Teams, a browser tab), Mad Light watches the **monitor source of the default audio sink** — the same stream you already hear on headphones or speakers — and shows a compact always-on-top **card**: a center heat circle (green / amber / red / idle grey) with a **simple color face** (bundled Twemoji PNG) and a **headphone badge** (on = listening, off / set aside = paused), plus one scrolling **speech-energy** strip. Optional frequency-band meters stay behind the gear.

Heat is a **talk-over / room-escalation** cue: simultaneous speech and interrupted turn-taking on that mix. It is **not** a dashboard, **not** a labeled pill, **not** emotion AI, **not** face reading, **not** speaker diarization, **not** a transcript, and it does not call a cloud API. Faces are glanceable states (calm / rising / hot), not a claim that we read the room’s feelings.

This tree ships the atmosphere dial with **overlap-first** heat (the old “loudness ≈ mad” path is gone). The **clarity / facilitator** work (“point landed?”, reframe, a tiny commandments-style framework) is **v2+** in **[ROADMAP.md](ROADMAP.md)**. It is not implemented here. Rebuild from **[SPEC.md](SPEC.md)**.

License: [MIT](LICENSE). Center faces and the headphone badge are [Twemoji](https://github.com/jdecked/twemoji) PNGs (© Twitter, Inc and contributors, [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/)) — see [madlight/assets/NOTICE](madlight/assets/NOTICE). Classic Tk cannot render color emoji on Windows, so the circle composites those PNGs with Pillow instead of `create_text`. README is written so the repo can go public later; that timing is undecided.

UI ancestor: [The Point](https://github.com/parth4/point-overlay) is inspiration only. This repo does not copy that YouTube / manual engine.

The git slug may stay `mad-lite`; the product and Python package are **Mad Light** / `madlight`.

## Who it’s for

These are the north-star uses. They are why the light exists. Today it still only shows **heat** — talk-over on the mix you already hear.

**Parth in live 2–5 person video calls.** A private, local, real-time glanceable cue when the room is escalating (people talking over each other, turns stacking) so he can soften or steer. Low lag, local/private, trustworthy enough to act on. Not a manager dashboard and not offline-only analysis.

**Accessibility / neurodiversity-minded.** A simple **non-verbal ambient cue** when conversation heat rises — glanceable, no transcript to parse. **Not a medical device.** No diagnosis, no “detects ADHD / autism / anxiety,” no clinical claims, no emotion detection.

**Executive / cryptic meetings** (personal use case). When an ask is restated and still does not land, the later product should cue a **reframe** (say it differently; check understanding). That facilitator behavior is the **v2+ arc**, not this release.

## How you get it

1. **Runnable local app** — this repo, **Omarchy / Linux first**. Install, run `madlight`, watch the default-sink monitor. Compact floating card: heat circle + simple 🙂 face + headphone on/off + one energy strip.
2. **Spec for another agent** — give a coding agent **[SPEC.md](SPEC.md)** (“build Mad Light to this spec”). Optionally add [`.cursor/skills/mad-light/SKILL.md`](.cursor/skills/mad-light/SKILL.md). The expected result is a faithful **local dial** whose yellow/red mean **talk-over**, not the roadmap’s coach features.

## What it does

| Face + headphones + circle | Meaning (talk-over, not emotion) |
| --- | --- |
| **🙂 🎧 on, green** | listening, calm — no sustained talk-over |
| **😬 🎧 on, amber** | listening, rising — sustained overlap / interrupted turns |
| **😡 🎧 on, red** | listening, hot — heavier, longer talk-over |
| **🙂 🎧 on, dark grey** | listening, near-silence (armed — still capturing) |
| **🎧 off / down, dark grey** | paused — not listening, capture off |

Headphones **on** the circle means the dial is listening. Headphones **down / set aside** means paused. Click the center to toggle. Calm is a simple 🙂 — not a blushy 😊. Rising 😬 and hot 😡 stay the glanceable heat arc.

The overlay is a **compact floating card** (Voice Access–style chrome, not a dashboard): **Tune + / −** (this heat feels right / wrong), drag handle, close, a **center circle** (click = pause ↔ listen), gear / help, and **one waveform** under the circle. There are **no** fixed “3 voice” lines on the default card. The tray icon mirrors the circle color. **Pause** is a click on the center (Space is an optional shortcut; also Escape / tray). Pause **stops capture immediately** (same kill switch as `--text` `off` / `pause`). Drag the handle or card to move; close quits.

**Tuning** is the self-improve path — not hidden: the chrome says **Tune**, +/− flash when you rate the heat, hover tips explain them, and the **gear** opens a Tuning panel (sensitivity: lower / default / higher). Help documents the same. Ratings and sensitivity write **local** files only — no audio, no cloud.

Yellow waits for a **dwell** (~0.7 s of overlap) so one emphatic word does not flip the dial. A loud monologue stays green. The waveform is slower than a raw block meter (EMA + a longer stride). A tiny caption on the card says **talk-over · not emotion**.

- Linux: `~/.config/madlight/prefs.json` and `feedback.jsonl`
- Windows: `%APPDATA%\madlight\`
- Override the directory with `MADLIGHT_CONFIG_DIR`

`feedback.jsonl` is one JSON object per line. Schema **2** (overlap-first) is documented in [CALIBRATE.md](CALIBRATE.md) and `madlight/feedback.py`: `schema`, `ts`, `label`, `level`, `overlap`, `rms`, `slope`, envelope cues (`fill` / `crest` / `cv` / `tightness` / `f0s`), and the cuts in force. After five thumbs-down of the same kind (too hot vs too cold), overlap (and RMS) cuts nudge slightly and persist.

Recompute from recent thumbs (his VC mix, not a universal model):

```bash
madlight calibrate --from-feedback --write-prefs
# alias:
madlight recalibrate --write-prefs
```

The card gear **Apply Tune ratings** runs the same fit. `--from-feedback` without `--write-prefs` only prints proposed `--overlap-rising` / `--overlap-hot`.

## Privacy

- Completely offline. The audio path is process-local: Pulse/PipeWire monitor → RAM → RMS numbers → a color.
- **Default: does not write audio or transcripts to disk.** There is no recorder, no WAV dump, no ASR.
- **Does not fall back to the microphone.** If the default sink has no monitor, Mad Light exits with instructions instead of opening a mic.
- `--allow-mic` exists for debugging and is a footgun; leave it off.

## Requirements

- Linux with **PipeWire** or **PulseAudio** (primary target: Omarchy / Arch-like).
- Python **3.11+**
- Headphones **or** speakers work when that device is the **default sink**. Headphones must work if they are default; you do not need speakers.

Arch / Omarchy:

```bash
sudo pacman -S python python-pip pipewire pipewire-pulse libpulse
# LED overlay:
sudo pacman -S tk
# tray (Waybar / StatusNotifier) — the kill switch:
sudo pacman -S python-gobject libappindicator-gtk3
```

`pactl` (from `libpulse` / `pipewire-pulse`) and optionally `parec` or `pw-record` make capture more reliable if `soundcard` cannot open the loopback.

## Install

```bash
git clone https://github.com/parth4/mad-lite.git
cd mad-lite

# uv
uv venv && source .venv/bin/activate
uv pip install -e .

# or pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Dev tests:

```bash
pip install -e ".[dev]"
pytest
```

## Run

```bash
madlight
# or
python -m madlight
# repo-slug alias:
madlite
```

Useful flags:

| Flag | |
| --- | --- |
| `--list-sources` | Print sink **monitors** (not mics) and mark the default |
| `--source NAME` | Use an explicit `.monitor` source |
| `--demo` | Synthetic energy loop; no audio device |
| `--text` | Print `idle` / `calm` / `rising` / `hot` / `paused` on stdout (good over SSH) |
| `--no-dot` / `--no-tray` | One surface only |
| `--backend auto\|soundcard\|parec\|pw-record` | Capture backend |
| `--rising-rms` `--hot-rms` `--rising-slope` | Secondary room-energy cuts (do not promote alone) |
| `--overlap-rising` `--overlap-hot` | Primary talk-over cuts (0..1) |

Pause / kill switch: click the **center circle** (or Space / Escape), tray **Pause — stop listening**, gear / right-click **Tuning…**, or in `--text` mode type `off` / `pause` / `q` + Enter (or Ctrl+C). Headphones on the circle = listening; headphones off = paused. Drag the handle (or the card) to move. Help explains faces, headphones, Tuning, and that the strip is energy — not voices.

### One energy strip — not voices

The bar under the face is a **smoothed speech-energy / waveform** of the same loopback mix. It is **not** speaker diarization, **not** “who is talking,” and it is **not** a fixed set of voice lines.

Optional **band meters** (gear → Tuning → “Show band meters”) split that mix into low / mid / high **frequency bands**. They are still one mix — not “Person 1/2/3”, not a fake 3-speaker view. Real multi-speaker ID is out of scope.

## Headphone sink monitor

Mad Light records **what you hear**, not what you say.

1. Put the meeting on your headphones and make them the default output.
2. Confirm:

   ```bash
   pactl get-default-sink
   # e.g. alsa_output.usb-Your_Headset.analog-stereo

   madlight --list-sources
   # expect: <that-sink>.monitor   (marked *)
   ```

3. Play two voices talking over each other (or `madlight --demo`). The LED should go amber/red on sustained overlap, then dark grey (idle) once energy stays below the silence floor. A single loud talker should stay green.

If the LED stays green while people pile on, you are on the wrong source (or a muted monitor). Pass `--source` from `--list-sources`. Do **not** pick `alsa_input.*` (that is the mic).

PipeWire and Pulse both expose a monitor on the active sink. Switching default output from speakers to headphones moves the monitor with it.

### Omarchy / Hyprland

The LED is a tiny always-on-top Tk window (often via XWayland). If it is tiled or buried:

```
windowrulev2 = float, title:^(Mad Light)$
windowrulev2 = pin, title:^(Mad Light)$
windowrulev2 = noborder, title:^(Mad Light)$
```

The tray icon is the Wayland-friendly pause switch and color mirror.

## How to test (no meeting required)

```bash
# 1. Classifier only — no mic, no Pulse:
pytest

# 2. Synthetic LED / text (still no device):
madlight --demo --text
# expect a ~10s loop: idle (near-silence) → two-voice overlap (rising) → denser overlap (hot) → fade
# type pause + Enter to freeze capture (dark grey / "paused")

# 3. Synthetic GUI (no meeting):
madlight --demo --no-tray
# floating card: grey + 🙂 + 🎧 on when silent (still listening);
# grey + 🎧 off / set aside when paused;
# green/amber/red + 🙂/😬/😡 + 🎧 on when talk-over;
# one waveform under the face (no 3-band “voices” unless you enable them in Tuning)
# click the center to pause / resume; Tune +/− rates the heat; × closes

# 4. Real playback through headphones:
#    play a video locally, default sink = headphones, then:
madlight --list-sources
madlight
```

Success looks like: fresh clone → install → run → monitor of the default sink → the **dot** stays green on a loud monologue and goes amber/red on sustained talk-over. No network in the audio path.

## Calibrate (offline critic)

Label short clips and score the same thresholds the LED uses. Not neural training, not the cloud.

```bash
madlight calibrate --manifest tests/fixtures/manifest.json
madlight calibrate --manifest samples/manifest.csv
```

Files default to **peak-normalize** (YouTube LUFS ≠ live volume). `--no-normalize` is absolute RMS, like the monitor. Priority fixture class: **crosstalk** (`expected_level=rising` or `hot`). See [CALIBRATE.md](CALIBRATE.md) and [samples/README.md](samples/README.md).

## Tuning

Defaults target **2–5 person video calls** on a hot loopback / loud meeting master. **Yellow / red mean sustained talk-over**, not one loud word:

- Primary: `overlap_rising = 0.48`, `overlap_hot = 0.86` (0..1 talk-over score)
- Score = dual independent F0s in 80–400 Hz (two talkers in the mix) + envelope fill/crest/short-gap tightness over ~1 s. Steady music (flat CV) stays out.
- Secondary room energy: `rising_rms = 0.08`, `hot_rms = 0.22`, `rising_slope = 0.14` — may shave the overlap cut a little once overlap is already present. **They do not promote alone.**
- 50 ms blocks, 100 ms F0 window, 1 s overlap window, 0.6 s slope window
- idle grey uses `silence_rms = 0.008`
- overlap must hold `rise_dwell_seconds = 0.70` before calm→rising, then `hot_dwell_seconds = 0.40` before rising→hot
- meters: one waveform bar every 6 blocks (~300 ms); incoming RMS uses EMA 0.12; optional band meters use EMA 0.08

`--text` prints `overlap`, `rms`, `slope`, and dBFS. Nudge `--overlap-rising` / `--overlap-hot`, or **Tune + / −** and gear **Tuning** (sensitivity + **Apply Tune ratings**). Higher sensitivity lowers the overlap bar. Quiet Linux headphone mixes and hot WASAPI loopbacks should prefer thumbs / `--from-feedback` over guessing universal RMS flags. Idle listening vs paused are the same grey; headphones on (🙂 armed) vs headphones off (cans set aside).

## Windows

WASAPI loopback via `soundcard` (same `--backend` as Linux):

```bash
madlight --backend soundcard
```

Loopback gain is often much hotter than a Linux headphone sink (meeting mix near full scale). Overlap-first heat is mostly level-invariant (two F0s in the mix), so a hot master should not yellow on normal turn-taking. If it still does, raise `--overlap-rising` or pick **Lower** sensitivity; if real pile-ons stay green, **Higher** or `--from-feedback`. Use `--demo` first if you want to see grey (silence / pause), heat colors, **crisp color faces + headphone on/off**, and the energy strip without a meeting. The heat disc (and gear / help) is a 4× Pillow ellipse composited with those Twemoji PNGs — not a Tk `create_oval` — so the ring stays smooth on Windows. The center uses bundled Twemoji PNGs (not Segoe/Noto emoji fonts) so Windows shows the same simple 🙂 / 😬 / 😡 faces and 🎧 badge as Linux. Tray may be missing on some desktops; click the center (or Space) still pauses.

## PyInstaller (optional)

Not a signed installer. From a Linux box with the same PipeWire/Pulse stack:

```bash
pip install pyinstaller
pyinstaller -F -n madlight -m madlight
```

You still need system `libpulse` / PipeWire on the target machine. This is a note, not a release pipeline.

## Roadmap

The heat LED is what this repo ships (overlap-first). Intent only — [ROADMAP.md](ROADMAP.md):

1. ~~Stacking / interrupt signals~~ — landed as the **heat driver** (not a second pip)
2. **Clarity / facilitator arc:** “point landed?” / reframe + a tiny commandments-style coach — not a note-taker
3. Dual local guides, both sides opt in
4. Skills / hooks so other apps **may** adopt; we do not claim Zoom or Teams will

## Out of scope

Whisper / ASR, speaker ID / diarization (the waveform and optional band meters are energy / frequency, not people), emotion / face analysis, Point faces, cloud APIs, auto-update, signed installers, writing meeting audio to disk. Talk-over here is **classical DSP on the mix**, not “who said what.”
