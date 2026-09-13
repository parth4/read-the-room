# Mad Light

**MAD = Meeting Atmosphere Dial.** **Light** = a signal / bulb — not “lite” as in a cut-down edition.

While a meeting plays on this machine (Zoom, Teams, a browser tab), Mad Light watches the **monitor source of the default audio sink** — the same stream you already hear on headphones or speakers — and shows a **recording-indicator LED**: a tiny always-on-top colored **dot** (green / amber / red) from crude energy features (rolling RMS and its short-term slope).

It is **not** a dashboard, **not** a labeled pill, **not** an emotion detector, **not** face reading, **not** a transcript, and it does not call a cloud API.

This tree is **v0 only** — the atmosphere dial. Later local stacking cues, facilitator prompts, dual opt-in guides, and optional app hooks are sketched in **[ROADMAP.md](ROADMAP.md)**. They are not implemented here.

License: [MIT](LICENSE). README is written so the repo can go public later; that timing is undecided.

UI ancestor: [The Point](https://github.com/parth4/point-overlay) is inspiration only. This repo does not copy that YouTube / manual engine.

The git slug may stay `mad-lite`; the product and Python package are **Mad Light** / `madlight`.

## What it does

| LED | Meaning (energy only) |
| --- | --- |
| **green** | calm — quiet / steady low energy |
| **amber** | rising — mid energy, or energy climbing quickly |
| **red** | hot — high RMS |
| **grey** | off — not listening |

The overlay is a **single circle**, about the size of a Zoom recording pip or a hardware LED. No status text on the dot. The tray icon mirrors the same colors. **Off — stop listening** lives on the tray (right-click the dot if you have no tray). Off **stops capture immediately**.

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
| `--text` | Print `calm` / `rising` / `hot` on stdout (good over SSH) |
| `--no-dot` / `--no-tray` | One surface only |
| `--backend auto\|soundcard\|parec\|pw-record` | Capture backend |
| `--rising-rms` `--hot-rms` `--rising-slope` | Thresholds (LED colors stay green / amber / red) |

Kill switch: tray **Off — stop listening**, right-click the LED, or in `--text` mode type `off` / `q` + Enter (or Ctrl+C).

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

3. Play something loud, then pause it. The LED should go red/amber, then green.

If the LED stays green while you hear the meeting, you are on the wrong source (or a muted monitor). Pass `--source` from `--list-sources`. Do **not** pick `alsa_input.*` (that is the mic).

PipeWire and Pulse both expose a monitor on the active sink. Switching default output from speakers to headphones moves the monitor with it.

### Omarchy / Hyprland

The LED is a tiny always-on-top Tk window (often via XWayland). If it is tiled or buried:

```
windowrulev2 = float, title:^(Mad Light)$
windowrulev2 = pin, title:^(Mad Light)$
windowrulev2 = noborder, title:^(Mad Light)$
```

The tray icon is the Wayland-friendly Off switch and color mirror.

## How to test (no meeting required)

```bash
# 1. Classifier only — no mic, no Pulse:
pytest

# 2. Synthetic LED / text (still no device):
madlight --demo --text
# expect a ~10s loop: calm → rising → hot → fade

# 3. Real playback through headphones:
#    play a video locally, default sink = headphones, then:
madlight --list-sources
madlight
```

Success looks like: fresh clone → install → run → monitor of the default sink → the **dot** reacts to loud vs quiet playback. No network in the audio path.

## Tuning

Defaults are conservative for speech-ish meeting playback:

- `rising_rms = 0.045`, `hot_rms = 0.11` (linear amplitude, 0..1)
- `rising_slope = 0.035` (RMS per second)
- 50 ms blocks, 2 s RMS window, 0.6 s slope window, hysteresis via `drop_margin`

`--text` prints `rms`, `slope`, and dBFS so you can nudge `--hot-rms` / `--rising-rms` if your headset mix is very quiet or very hot. The LED stays three colors plus grey-off.

## Windows (later)

v0 is Linux. A later port can use WASAPI loopback (`soundcard` already speaks WASAPI). That is explicitly out of scope here and must not block this tree.

## PyInstaller (optional)

Not a signed installer. From a Linux box with the same PipeWire/Pulse stack:

```bash
pip install pyinstaller
pyinstaller -F -n madlight -m madlight
```

You still need system `libpulse` / PipeWire on the target machine. This is a note, not a release pipeline.

## Roadmap

**This repo is v0** (the heat LED). The rest is intent only — [ROADMAP.md](ROADMAP.md):

1. Stacking / interrupt **signals** from local audio (still no transcript)
2. “Point landed?” / reframe cues and a tiny coach framework — not a note-taker
3. Dual local guides, both sides opt in
4. Skills / hooks so other apps **may** adopt; we do not claim Zoom or Teams will

## Out of scope (v0)

Whisper / ASR, speaker ID, talk-over detection, Point faces, cloud APIs, auto-update, signed installers, writing meeting audio to disk. Talk-over as a **local feature** is a v1 idea, not this release.
