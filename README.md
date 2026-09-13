# Mad Light

**MAD = Meeting Atmosphere Dial.** **Light** = a signal / bulb — not “lite” as in a cut-down edition.

While a meeting plays on this machine (Zoom, Teams, a browser tab), Mad Light watches the **monitor source of the default audio sink** — the same stream you already hear on headphones or speakers — and shows a **recording-indicator LED**: a tiny always-on-top colored **dot** (green / amber / red) from crude energy features (rolling RMS and its short-term slope), plus a compact scrolling level and three **activity lanes** (frequency bands of the mix).

It is **not** a dashboard, **not** a labeled pill, **not** an emotion detector, **not** face reading, **not** speaker diarization, **not** a transcript, and it does not call a cloud API.

This tree is **v0 only** — the atmosphere dial. The **clarity / facilitator** work (“point landed?”, reframe, a tiny commandments-style framework) is **v2+** in **[ROADMAP.md](ROADMAP.md)**. It is not implemented here. Rebuild v0 from **[SPEC.md](SPEC.md)**.

License: [MIT](LICENSE). README is written so the repo can go public later; that timing is undecided.

UI ancestor: [The Point](https://github.com/parth4/point-overlay) is inspiration only. This repo does not copy that YouTube / manual engine.

The git slug may stay `mad-lite`; the product and Python package are **Mad Light** / `madlight`.

## Who it’s for

These are the north-star uses. They are why the light exists. **v0 still only shows heat.**

**Accessibility / neurodiversity-minded.** A simple **non-verbal ambient cue** when conversation heat rises, or when an ask is not landing — glanceable, no transcript to parse. **Not a medical device.** No diagnosis, no “detects ADHD / autism / anxiety,” no clinical claims.

**Executive / cryptic meetings** (personal use case). When an ask is restated and still does not land, the later product should cue a **reframe** (say it differently; check understanding). That facilitator behavior is the **v2+ arc**, not this release. Today the LED only moves with **energy**.

## How you get it

1. **Runnable local app** — this repo, **Omarchy / Linux first**. Install, run `madlight`, watch the default-sink monitor. Compact LED + level + activity lanes.
2. **Spec for another agent** — give a coding agent **[SPEC.md](SPEC.md)** (“build Mad Light to this spec”). Optionally add [`.cursor/skills/mad-light/SKILL.md`](.cursor/skills/mad-light/SKILL.md). The expected result is a faithful **local dial + recording-indicator dot**, not the roadmap’s coach features.

## What it does

| LED | Meaning (energy only) |
| --- | --- |
| **green** | calm — listening, steady low-but-present energy |
| **amber** | rising — mid energy, or energy climbing quickly |
| **red** | hot — high RMS |
| **dark grey** | paused, or sustained near-silence (not listening / idle) |

The overlay is a **compact strip**: a Zoom-pip-sized **dot**, a short scrolling level (the same capture blocks that feed heat), and **three thin activity lanes** (low / mid / high bands of the loopback mix). No speaker names. The tray icon mirrors the LED color. **Pause listening** is a click on the strip, Space / Escape, the right-click menu, or the tray. Pause **stops capture immediately** (same kill switch as `--text` `off` / `pause`).

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
| `--rising-rms` `--hot-rms` `--rising-slope` | Thresholds (LED colors stay green / amber / red) |

Pause / kill switch: click the strip (or Space / Escape), tray **Pause — stop listening**, right-click the LED, or in `--text` mode type `off` / `pause` / `q` + Enter (or Ctrl+C). Click-drag still moves the window.

### Activity lanes ≠ speakers

The three lines are **frequency bands** (low / mid / high) of the same loopback mix — a local, honest stand-in for concurrent activity. They are **not** speaker diarization, **not** “Person 1/2/3”, and they do not identify who is talking. Real multi-speaker ID is out of scope.

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

3. Play something loud, then pause it. The LED should go red/amber, then dark grey (idle) once energy stays below the silence floor.

If the LED stays green while you hear the meeting, you are on the wrong source (or a muted monitor). Pass `--source` from `--list-sources`. Do **not** pick `alsa_input.*` (that is the mic).

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
# expect a ~10s loop: idle (near-silence) → rising → hot → fade
# type pause + Enter to freeze capture (dark grey / "paused")

# 3. Synthetic GUI (no meeting):
madlight --demo --no-tray
# grey while silent or paused; green/amber/red when energy;
# waveform scrolls; three activity lanes move independently

# 4. Real playback through headphones:
#    play a video locally, default sink = headphones, then:
madlight --list-sources
madlight
```

Success looks like: fresh clone → install → run → monitor of the default sink → the **dot** reacts to loud vs quiet playback. No network in the audio path.

## Calibrate (offline critic)

Label short clips and score the same thresholds the LED uses. Not neural training, not the cloud.

```bash
madlight calibrate --manifest tests/fixtures/manifest.json
madlight calibrate --manifest samples/manifest.csv
```

Files default to **peak-normalize** (YouTube LUFS ≠ live volume). `--no-normalize` is absolute RMS, like the monitor. Priority fixture class: **crosstalk** (`expected_level=rising` in v0). See [CALIBRATE.md](CALIBRATE.md) and [samples/README.md](samples/README.md).

## Tuning

Defaults are conservative for speech-ish meeting playback:

- `rising_rms = 0.045`, `hot_rms = 0.11` (linear amplitude, 0..1)
- `rising_slope = 0.07` (RMS per second)
- 50 ms blocks, 2 s RMS window, 0.6 s slope window, hysteresis via `drop_margin`
- idle grey uses the same `silence_rms = 0.008` floor as the classifier (smoothed RMS)

`--text` prints `rms`, `slope`, and dBFS so you can nudge `--hot-rms` / `--rising-rms` if your headset mix is very quiet or very hot. The LED stays three heat colors plus dark grey (paused / idle).

## Windows

WASAPI loopback via `soundcard` (same `--backend` as Linux):

```bash
madlight --backend soundcard
```

Use `--demo` first if you want to see grey (silence / pause), heat colors, the scrolling level, and the three activity lanes without a meeting. Tray may be missing on some desktops; click or Space still pauses.

## PyInstaller (optional)

Not a signed installer. From a Linux box with the same PipeWire/Pulse stack:

```bash
pip install pyinstaller
pyinstaller -F -n madlight -m madlight
```

You still need system `libpulse` / PipeWire on the target machine. This is a note, not a release pipeline.

## Roadmap

**This repo is v0** (the heat LED). Intent only — [ROADMAP.md](ROADMAP.md):

1. Stacking / interrupt **signals** from local audio (still no transcript)
2. **Clarity / facilitator arc:** “point landed?” / reframe + a tiny commandments-style coach — not a note-taker
3. Dual local guides, both sides opt in
4. Skills / hooks so other apps **may** adopt; we do not claim Zoom or Teams will

## Out of scope (v0)

Whisper / ASR, speaker ID / diarization (activity lanes are frequency bands, not people), talk-over detection, Point faces, cloud APIs, auto-update, signed installers, writing meeting audio to disk. Talk-over as a **local feature** is a v1 idea, not this release.
