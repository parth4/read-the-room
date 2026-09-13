# Mad Lite

**MAD = Meeting Atmosphere Dial.** A tiny, local-only desktop heat pill.

While a meeting plays on this machine (Zoom, Teams, a browser tab), Mad Lite watches the **monitor source of the default audio sink** — the same stream you already hear on headphones or speakers — and shows a green / amber / red pill from crude energy features (rolling RMS and its short-term slope).

It is **not** an emotion detector, **not** face reading, **not** a transcript, and it does not call a cloud API.

This tree is **v0 only** — the heat dial. Later local stacking cues, facilitator prompts, dual opt-in guides, and optional app hooks are sketched in **[ROADMAP.md](ROADMAP.md)**. They are not implemented here.

License: [MIT](LICENSE). Written as a public-destined repo: use it, credit it, bake pieces in.

UI ancestor: [The Point](https://github.com/parth4/point-overlay) is inspiration only. This repo does not copy that YouTube / manual engine.

## What it does

| Pill | Meaning (energy only) |
| --- | --- |
| **CALM** (green) | Quiet / steady low energy |
| **RISING** (amber) | Mid energy, or energy climbing quickly |
| **HOT** (red) | High RMS |

Off (tray or the pill **Off** button) **stops capture immediately**. That is the kill switch.

## Privacy

- Completely offline. The audio path is process-local: Pulse/PipeWire monitor → RAM → RMS numbers → a color.
- **Default: does not write audio or transcripts to disk.** There is no recorder, no WAV dump, no ASR.
- **Does not fall back to the microphone.** If the default sink has no monitor, Mad Lite exits with instructions instead of opening a mic.
- `--allow-mic` exists for debugging and is a footgun; leave it off.

## Requirements

- Linux with **PipeWire** or **PulseAudio** (primary target: Omarchy / Arch-like).
- Python **3.11+**
- Headphones **or** speakers work when that device is the **default sink**. Headphones must work if they are default; you do not need speakers.

Arch / Omarchy:

```bash
sudo pacman -S python python-pip pipewire pipewire-pulse libpulse
# pill:
sudo pacman -S tk
# tray (Waybar / StatusNotifier):
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
madlite
# or
python -m madlite
```

Useful flags:

| Flag | |
| --- | --- |
| `--list-sources` | Print sink **monitors** (not mics) and mark the default |
| `--source NAME` | Use an explicit `.monitor` source |
| `--demo` | Synthetic energy loop; no audio device |
| `--text` | Print `calm` / `rising` / `hot` on stdout (good over SSH) |
| `--no-pill` / `--no-tray` | One surface only |
| `--backend auto\|soundcard\|parec\|pw-record` | Capture backend |
| `--rising-rms` `--hot-rms` `--rising-slope` | Thresholds |

Kill switch: pill **Off**, tray **Off — stop listening**, or in `--text` mode type `off` / `q` + Enter (or Ctrl+C).

## Headphone sink monitor

Mad Lite records **what you hear**, not what you say.

1. Put the meeting on your headphones and make them the default output.
2. Confirm:

   ```bash
   pactl get-default-sink
   # e.g. alsa_output.usb-Your_Headset.analog-stereo

   madlite --list-sources
   # expect: <that-sink>.monitor   (marked *)
   ```

3. Play something loud, then pause it. The pill should go hot/rising, then calm.

If the pill stays calm while you hear the meeting, you are on the wrong source (or a muted monitor). Pass `--source` from `--list-sources`. Do **not** pick `alsa_input.*` (that is the mic).

PipeWire and Pulse both expose a monitor on the active sink. Switching default output from speakers to headphones moves the monitor with it.

### Omarchy / Hyprland

The pill is a tiny always-on-top Tk window (often via XWayland). If it is tiled or buried:

```
windowrulev2 = float, title:^(Mad Lite)$
windowrulev2 = pin, title:^(Mad Lite)$
```

The tray icon is the Wayland-friendly Off switch.

## How to test (no meeting required)

```bash
# 1. Classifier only — no mic, no Pulse:
pytest

# 2. Synthetic pill / text (still no device):
madlite --demo --text
# expect a ~10s loop: calm → rising → hot → fade

# 3. Real playback through headphones:
#    play a video locally, default sink = headphones, then:
madlite --list-sources
madlite
```

Success looks like: fresh clone → install → run → monitor of the default sink → pill reacts to loud vs quiet playback. No network in the audio path.

## Tuning

Defaults are conservative for speech-ish meeting playback:

- `rising_rms = 0.045`, `hot_rms = 0.11` (linear amplitude, 0..1)
- `rising_slope = 0.035` (RMS per second)
- 50 ms blocks, 2 s RMS window, 0.6 s slope window, hysteresis via `drop_margin`

`--text` prints `rms`, `slope`, and dBFS so you can nudge `--hot-rms` / `--rising-rms` if your headset mix is very quiet or very hot.

## Windows (later)

v0 is Linux. A later port can use WASAPI loopback (`soundcard` already speaks WASAPI). That is explicitly out of scope here and must not block this tree.

## PyInstaller (optional)

Not a signed installer. From a Linux box with the same PipeWire/Pulse stack:

```bash
pip install pyinstaller
pyinstaller -F -n madlite -m madlite
# or: pyinstaller -F -n madlite $(which madlite)
```

You still need system `libpulse` / PipeWire on the target machine. This is a note, not a release pipeline.

## Roadmap

**This repo is v0** (the heat dial). The rest is intent only — [ROADMAP.md](ROADMAP.md):

1. Stacking / interrupt **signals** from local audio (still no transcript)
2. “Point landed?” / reframe cues and a tiny coach framework — not a note-taker
3. Dual local guides, both sides opt in
4. Skills / hooks so other apps **may** adopt; we do not claim Zoom or Teams will

## Out of scope (v0)

Whisper / ASR, speaker ID, talk-over detection, Point faces, cloud APIs, auto-update, signed installers, writing meeting audio to disk. Talk-over as a **local feature** is a v1 idea, not this release.
