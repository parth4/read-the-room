# Calibrate — accuracy critic + thumbs fit

Offline, local, **not** neural training and **not** the cloud.

Two ways to tune the same `HeatConfig` the LED uses (`madlight/heat.py`):

1. **Labeled clips** — `madlight calibrate --manifest …` scores files and can `--propose` overlap cuts.
2. **His thumbs** — Tune + / − on the card append to local `feedback.jsonl`. Then:

```bash
madlight calibrate --from-feedback           # print fitted overlap cuts
madlight calibrate --from-feedback --write-prefs
madlight recalibrate --write-prefs           # same
```

The card gear **Apply Tune ratings** runs (2) and applies it live. Ratings and the resulting numbers stay on the machine. No audio is stored.

## Feedback schema (`feedback.jsonl`)

One JSON object per line. **Schema 2** = overlap-first. Canonical description: `madlight/feedback.py`.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | int | `2` on new lines. Omitted on older thumbs. |
| `ts` | string | UTC ISO-8601. |
| `label` | `up` \| `down` | This heat feels right / wrong. |
| `listening` | bool | Capture was on. |
| `idle` | bool | Near-silence (armed grey). |
| `level` | `calm` \| `rising` \| `hot` | Displayed heat at the tap. |
| `overlap` | number \| null | 0..1 talk-over score (**primary**). |
| `rms` `slope` `db_fs` | number \| null | Secondary room energy. |
| `fill` `crest` `cv` `tightness` `f0s` | number \| null | Envelope / dual-F0 cues. |
| `overlap_rising` `overlap_hot` | number | Cuts in force. |
| `rising_rms` `hot_rms` | number | Secondary RMS cuts in force. |

Older lines without `overlap` still count: the fitter rebuilds a density-only proxy from `fill` / `crest` / `cv`.

### How a thumb is read

- **down** on rising/hot (not idle) → false heat → raise the overlap bar (less sensitive).
- **down** on calm/idle → missed heat → lower the bar.
- **up** on rising/hot → true heat example.
- **up** on calm/idle → true calm example.

The fitter places `overlap_rising` between the high side of “should be calm” and the low side of “should be heat”, and `overlap_hot` from thumbs that named hot vs rising. Prefer this **VC-mix** fit over universal defaults.

After five downs of the same kind without running `--from-feedback`, overlap (and RMS) cuts also **nudge** a little on their own.

Linux: `~/.config/madlight/` — Windows: `%APPDATA%\madlight\` — override: `MADLIGHT_CONFIG_DIR`.

## Priority fixture: crosstalk

**Multiple people talking over each other** is the first class to collect. Label it `rising` or `hot` (sustained pile-on). A loud single voice is `calm`.

```csv
path,expected_level,category
overlap_panel.wav,rising,crosstalk
ted_single_voice.wav,calm,calm
argument_pileon.wav,hot,crosstalk
```

Local Omarchy workflow: yt-dlp cuts under `samples/` (gitignored wavs) + `samples/manifest.csv`. See [samples/README.md](samples/README.md).

CI does **not** need those blobs. `tests/fixtures/manifest.json` generates synths, including **crosstalk**, **loud_monologue**, **emphatic_word**, and **hot_master_overlap**.

## Files are not live volume

YouTube / TED **masters are loud**. Absolute RMS on the WAV can still dwarf a headphone sink.

Overlap-first heat is mostly **level-invariant** (two F0s in the mix), so peak-normalize is less load-bearing than it was for RMS-first heat. `madlight calibrate` still **peak-normalizes each file by default** (`0.30`). **`--no-normalize`** scores absolute RMS (same domain as the live LED).

```bash
madlight calibrate --manifest samples/manifest.csv
madlight calibrate --manifest samples/manifest.csv --no-normalize
madlight calibrate --manifest samples/manifest.csv --normalize-peak 0.24
```

The running app (`madlight` without `calibrate`) is unchanged: monitor audio is whatever you actually play.

## 1. Cut clips

Keep them short (2–10 s). Export PCM WAV. Put them in `samples/` (gitignored). Prefer **crosstalk**, plus calm monologue and hot pile-on.

## 2. Manifest

JSON array, JSONL, or CSV. Paths are relative to the manifest file.

```json
[
  {"path": "overlap.wav", "expected_level": "rising", "category": "crosstalk"},
  {"path": "ted_calm.wav", "expected_level": "calm", "category": "calm"},
  {"path": "pileon.wav", "expected_level": "hot", "category": "crosstalk"}
]
```

CSV headers: `path,expected_level,category`.

## 3. Run the critic

```bash
# synthetic fixtures (no real audio in git) — includes crosstalk + loud monologue
madlight calibrate --manifest tests/fixtures/manifest.json

# your yt-dlp / meeting cuts
madlight calibrate --manifest samples/manifest.csv --propose
```

`--propose` grid-searches `overlap_rising` / `overlap_hot`. If you used `--normalize` (default), listen-test before pasting onto `madlight`.

```text
proposed  accuracy=83%  --overlap-rising 0.48 --overlap-hot 0.86 --rising-rms 0.08 --hot-rms 0.22 --rising-slope 0.14
```

## How a clip is scored

Optional peak-normalize, then 50 ms blocks (same classifier as the LED). After warmup, **majority** level wins. A brief laugh or one emphatic word should not make a quiet clip `rising`.

## Privacy

Clips stay on your disk. No network, no model upload. Do not commit real meeting audio.

## Overlap (calm vs crosstalk)

The live LED path is **overlap-first**:

- two independent F0s in 80–400 Hz → talk-over
- full, low-crest, short-gap envelope → stacking / interrupted turns
- peaky monologue / one emphatic word → calm (dwell)
- flat music (CV ≈ 0, crest ≈ 1) → stays out
- RMS / slope may boost a little **after** overlap is present; they do not promote alone

Defaults target 2–5 person calls on a hot mix. Fit `--from-feedback` to *his* headset / WASAPI domain.
