# Mad Light

**MAD = Meeting Atmosphere Dial.** **Light** = a signal / bulb — not “lite” as in a cut-down edition.

While a meeting plays on this machine (Zoom, Teams, a browser tab), Mad Light watches the **monitor source of the default audio sink** — the same stream you already hear on headphones or speakers — and shows a compact always-on-top **card**: a center heat circle (green / amber / red / idle grey) with a **color face** (bundled Twemoji PNG), plus one scrolling **speech-energy** strip. Optional frequency-band meters stay behind the gear.

It is **not** a dashboard, **not** a labeled pill, **not** an emotion detector, **not** face reading, **not** speaker diarization, **not** a transcript, and it does not call a cloud API.

This tree is **v0 only** — the atmosphere dial. The **clarity / facilitator** work (“point landed?”, reframe, a tiny commandments-style framework) is **v2+** in **[ROADMAP.md](ROADMAP.md)**. It is not implemented here. Rebuild v0 from **[SPEC.md](SPEC.md)**.

License: [MIT](LICENSE). Center faces are [Twemoji](https://github.com/jdecked/twemoji) PNGs (© Twitter, Inc and contributors, [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/)) — see [madlight/assets/NOTICE](madlight/assets/NOTICE). Classic Tk cannot render color emoji on Windows, so the circle composites those PNGs with Pillow instead of `create_text`. README is written so the repo can go public later; that timing is undecided.

UI ancestor: [The Point](https://github.com/parth4/point-overlay) is inspiration only. This repo does not copy that YouTube / manual engine.

The git slug may stay `mad-lite`; the product and Python package are **Mad Light** / `madlight`.

## Who it’s for

These are the north-star uses. They are why the light exists. **v0 still only shows heat.**

**Accessibility / neurodiversity-minded.** A simple **non-verbal ambient cue** when conversation heat rises, or when an ask is not landing — glanceable, no transcript to parse. **Not a medical device.** No diagnosis, no “detects ADHD / autism / anxiety,” no clinical claims.

**Executive / cryptic meetings** (personal use case). When an ask is restated and still does not land, the later product should cue a **reframe** (say it differently; check understanding). That facilitator behavior is the **v2+ arc**, not this release. Today the LED only moves with **energy**.

## How you get it

1. **Runnable local app** — this repo, **Omarchy / Linux first**. Install, run `madlight`, watch the default-sink monitor. Compact floating card: heat circle + face + one energy strip.
2. **Spec for another agent** — give a coding agent **[SPEC.md](SPEC.md)** (“build Mad Light to this spec”). Optionally add [`.cursor/skills/mad-light/SKILL.md`](.cursor/skills/mad-light/SKILL.md). The expected result is a faithful **local dial + recording-indicator dot**, not the roadmap’s coach features.

## What it does

| Face + circle | Meaning (energy only) |
| --- | --- |
| **🙂 green** | listening, calm — steady low-but-present energy |
| **😐 amber** | listening, rising — mid energy, or energy climbing |
| **😠 red** | listening, hot — high RMS |
| **🙂 dark grey** | listening, near-silence (armed — still capturing) |
| **🤐 dark grey** | paused — not listening, capture off |

The overlay is a **compact floating card** (Voice Access–style chrome, not a dashboard): **Tune + / −** (this heat feels right / wrong), drag handle, close, a **center face** (click = pause ↔ listen), gear / help, and **one waveform** under the circle. There are **no** fixed “3 voice” lines on the default card. The tray icon mirrors the circle color. **Pause** is a click on the center face (Space is an optional shortcut; also Escape / tray). Pause **stops capture immediately** (same kill switch as `--text` `off` / `pause`). Drag the handle or card to move; close quits.

**Tuning** is the self-improve path — not hidden: the chrome says **Tune**, +/− flash when you rate the heat, hover tips explain them, and the **gear** opens a Tuning panel (sensitivity: lower / default / higher). Help documents the same. Ratings and sensitivity write **local** files only — no audio, no cloud.

Yellow waits for a **dwell** (~1.2 s of climb) so one emphatic word does not flip the dial. The waveform is slower than a raw block meter (EMA + a longer stride).

- Linux: `~/.config/madlight/prefs.json` and `feedback.jsonl`
- Windows: `%APPDATA%\madlight\`
- Override the directory with `MADLIGHT_CONFIG_DIR`

`feedback.jsonl` is one JSON object per line (`ts`, `label`, `level`, `rms`, `slope`, `fill` / `crest` / `cv`). After five thumbs-down of the same kind (too hot vs too cold), thresholds nudge slightly and persist. `madlight calibrate --from-feedback` is not implemented yet.

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

Pause / kill switch: click the **center face** (or Space / Escape), tray **Pause — stop listening**, gear / right-click **Tuning…**, or in `--text` mode type `off` / `pause` / `q` + Enter (or Ctrl+C). Drag the handle (or the card) to move. Help explains faces, Tuning, and that the strip is energy — not voices.

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
# floating card: grey + 🙂 when silent (still listening); grey + 🤐 when paused;
# green/amber/red + 🙂/😐/😠 when energy;
# one waveform under the face (no 3-band “voices” unless you enable them in Tuning)
# click the center face to pause / resume; Tune +/− rates the heat; × closes

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

Defaults target **2–5 person video calls** on a hot loopback / loud meeting master (normal talk stays green; amber/red for a real climb or talk-over):

- `rising_rms = 0.08`, `hot_rms = 0.22` (linear amplitude, 0..1)
- `rising_slope = 0.14` (RMS per second)
- density (talk-over) enters only when `rms >= rising_rms` — not the `silence_rms` floor
- 50 ms blocks, 2 s RMS window, 0.6 s slope window, hysteresis via `drop_margin`
- idle grey uses the same `silence_rms = 0.008` floor as the classifier (smoothed RMS)
- climb must hold `rise_dwell_seconds = 1.2` before calm→rising; density already integrates over the 2 s window
- meters: one waveform bar every 6 blocks (~300 ms); incoming RMS uses EMA 0.12; optional band meters use EMA 0.08 (slower than the previous stride-3 / 0.16 defaults)

`--text` prints `rms`, `slope`, and dBFS so you can nudge `--rising-rms` / `--hot-rms` / `--rising-slope`. Or use **Tune + / −** and gear **Tuning** (sensitivity) on the card. Quiet Linux headphone mixes may need **lower** flags; a still-hotter Windows loopback may need **higher** ones. Idle listening vs paused are the same grey, different faces (🙂 armed vs 🤐 muted).

## Windows

WASAPI loopback via `soundcard` (same `--backend` as Linux):

```bash
madlight --backend soundcard
```

Loopback gain is often much hotter than a Linux headphone sink (meeting mix near full scale). Defaults above are sized for that. If normal 2–5 person talk still goes amber in the first seconds, raise the flags and watch `--text`:

```bash
madlight --backend soundcard --rising-rms 0.10 --rising-slope 0.16 --hot-rms 0.26 --text
```

If the LED never leaves green on a quiet headset mix, lower `--rising-rms` / `--hot-rms` instead — or open **Tuning** and pick **Higher** sensitivity. Use `--demo` first if you want to see grey (silence / pause), heat colors, **crisp color faces**, and the energy strip without a meeting. The center uses bundled Twemoji PNGs (not Segoe/Noto emoji fonts) so Windows shows the same color faces as Linux. Tray may be missing on some desktops; click the face (or Space) still pauses.

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

Whisper / ASR, speaker ID / diarization (the waveform and optional band meters are energy / frequency, not people), talk-over detection, Point faces, cloud APIs, auto-update, signed installers, writing meeting audio to disk. Talk-over as a **local feature** is a v1 idea, not this release.
