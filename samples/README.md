# Sample clips (local)

Drop **your** meeting excerpts here. **Do not commit large media** — `*.wav` is gitignored.

The critic reads a **manifest** (see [CALIBRATE.md](../CALIBRATE.md)), not this folder blindly. Copy clips in, then list them in a JSONL/CSV/JSON manifest.

## Categories

| Category | What to cut | `expected_level` |
| --- | --- | --- |
| `calm` | Quiet discussion, one steady voice, low energy | `calm` |
| `rising` | Energy climbing — people leaning in, getting louder | `rising` |
| `hot` | Overlap, raised voices, the room is clearly hot | `hot` |
| `silence_or_music` | Hold music, waiting-room bed, dead air (**trap**) | usually `calm` — must not always be `hot` |
| `laughter_applause` | A laugh or clap burst in an otherwise calm stretch (**trap**) | usually `calm` if the burst is brief |

`expected_level` is only `calm` | `rising` | `hot` (the LED). `category` is extra context for the scorecard.

## Synthetic stand-ins

This repo does **not** ship real meetings. Tiny synthetic WAVs are generated on the fly from `tests/fixtures/manifest.json` (`synth` field) when you run `madlight calibrate`.

```bash
madlight calibrate --manifest tests/fixtures/manifest.json
```

Kinds the generator knows: `silence`, `calm`, `rising`, `hot`, `music_steady`, `laughter_burst`.
