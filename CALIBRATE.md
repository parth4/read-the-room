# Calibrate — accuracy critic

Offline, local, **not** neural training and **not** the cloud. You label short clips; Mad Light scores the **same** `HeatConfig` the LED uses (`madlight/heat.py`) and can **propose CLI flags**.

The v0 LED UI does not change. No thumbs-up on the pip (that is a later roadmap idea).

## 1. Cut clips

See [samples/README.md](samples/README.md). Keep them short (2–10 s). Export mono or stereo WAV (PCM). Put them anywhere local, e.g. `samples/inbox/` (gitignored).

## 2. Write a manifest

JSON array, JSONL, or CSV. Paths are relative to the manifest file.

```json
[
  {"path": "inbox/standup_quiet.wav", "expected_level": "calm", "category": "calm"},
  {"path": "inbox/ask_getting_loud.wav", "expected_level": "rising", "category": "rising"},
  {"path": "inbox/overlap.wav", "expected_level": "hot", "category": "hot"},
  {"path": "inbox/hold_music.wav", "expected_level": "calm", "category": "silence_or_music"},
  {"path": "inbox/laugh.wav", "expected_level": "calm", "category": "laughter_applause"}
]
```

JSONL is the same objects, one per line. CSV headers: `path,expected_level,category`.

## 3. Run the critic

```bash
# synthetic fixtures (no real audio in git):
madlight calibrate --manifest tests/fixtures/manifest.json

# your clips:
madlight calibrate --manifest samples/manifest.jsonl --propose
```

`--propose` runs a small **grid search** over `rising_rms` / `hot_rms` / `rising_slope` and prints suggested flags:

```text
proposed  accuracy=83%  --rising-rms 0.06 --hot-rms 0.14 --rising-slope 0.035
```

Paste those onto `madlight` (same process as `--demo`). Nothing is uploaded.

```bash
madlight --rising-rms 0.06 --hot-rms 0.14 --rising-slope 0.035
```

## How a clip is scored

The file is walked in 50 ms RMS blocks (same classifier as the LED). After a short warmup, the **majority** level is the prediction. A brief laugh spike should not flip a mostly-quiet clip to `hot`.

## Privacy

Clips stay on your disk. The critic does not call a network API and does not write models. Do not commit real meeting audio.
