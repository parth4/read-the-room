# Calibrate — accuracy critic

Offline, local, **not** neural training and **not** the cloud. You label short clips; Mad Light scores the **same** `HeatConfig` the LED uses (`madlight/heat.py`) and can **propose CLI flags**.

The v0 LED UI does not change. Live mic/monitor capture stays **absolute RMS**. No thumbs-up on the pip.

## Priority fixture: crosstalk

**Multiple people talking over each other** (crosstalk / stacking) is the first class to collect.

v0 has no stacking detector. In the manifest, label crosstalk as **`expected_level=rising`** (heat is up; who-talks-over-whom is **v1**).

```csv
path,expected_level,category
overlap_panel.wav,rising,crosstalk
ted_single_voice.wav,calm,calm
shouting.wav,hot,hot
```

Local Omarchy workflow: yt-dlp cuts under `samples/` (gitignored wavs) + `samples/manifest.csv`. See [samples/README.md](samples/README.md).

CI does **not** need those blobs. `tests/fixtures/manifest.json` generates a tiny **`crosstalk`** synth (two overlapping tones).

## Files are not live volume

YouTube / TED **masters are loud**. Absolute RMS on the WAV can still dwarf a headphone sink, even with the raised live defaults (`rising_rms=0.08`, `hot_rms=0.22`). Hearing the same clip through headphones is a different level (sink volume, not file LUFS).

`madlight calibrate` **peak-normalizes each file by default** to a modest target peak (`0.30`, paired with those live defaults) so thresholds stay in a headphone-like domain. **`--no-normalize`** scores absolute RMS (same domain as the live LED).

```bash
# default: peak-normalize files (recommended for YouTube cuts)
madlight calibrate --manifest samples/manifest.csv

# live-domain score (hot WASAPI / meeting-master files)
madlight calibrate --manifest samples/manifest.csv --no-normalize

# optional target peak (default 0.30)
madlight calibrate --manifest samples/manifest.csv --normalize-peak 0.24
```

The running app (`madlight` without `calibrate`) is unchanged: monitor RMS is whatever you actually play.

## 1. Cut clips

Keep them short (2–10 s). Export PCM WAV. Put them in `samples/` (gitignored). Prefer **crosstalk**, plus calm and hot.

## 2. Manifest

JSON array, JSONL, or CSV. Paths are relative to the manifest file.

```json
[
  {"path": "overlap.wav", "expected_level": "rising", "category": "crosstalk"},
  {"path": "ted_calm.wav", "expected_level": "calm", "category": "calm"},
  {"path": "shout.wav", "expected_level": "hot", "category": "hot"}
]
```

CSV headers: `path,expected_level,category`.

## 3. Run the critic

```bash
# synthetic fixtures (no real audio in git) — includes crosstalk
madlight calibrate --manifest tests/fixtures/manifest.json

# your yt-dlp / meeting cuts
madlight calibrate --manifest samples/manifest.csv --propose
```

`--propose` grid-searches `rising_rms` / `hot_rms` / `rising_slope`. If you used `--normalize` (default), those flags are for the **normalized file domain**. Live playback volume ≠ file LUFS — **listen-test** before pasting onto `madlight`.

```text
proposed  accuracy=83%  --rising-rms 0.08 --hot-rms 0.22 --rising-slope 0.14
note: flags are for this file-scoring mode. Live playback volume ≠ file LUFS.
```

## How a clip is scored

Optional peak-normalize, then 50 ms RMS blocks (same classifier as the LED). After warmup, **majority** level wins. A brief laugh should not make a quiet clip `hot`.

## Privacy

Clips stay on your disk. No network, no model upload. Do not commit real meeting audio.

## Density (calm vs crosstalk)

The live LED path is absolute RMS, plus a **density** cue:

- calm turn-taking speech is peaky with gaps → high crest
- talk-over / heated stretch is fuller → high fill, lower crest, some modulation (`cv`)
- flat music is full but `cv ≈ 0` → stays out of the density path
- density enter also requires `rms >= rising_rms` (not `silence_rms`) so a hot master / WASAPI loopback does not go amber on normal VC talk

Defaults target 2–5 person calls on a hot mix. Peak-normalize is for synth/CI; do not expect real talk-over to score the same under `--normalize`.

