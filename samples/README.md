# Sample clips (local)

**Priority class: crosstalk** — multiple people talking over each other (stacking). That is the finding that started this folder.

On a local Omarchy box you may already have **yt-dlp cuts** here (gitignored `*.wav`) plus `manifest.csv`. **Do not commit those blobs.**

The critic reads a **manifest**, not the directory blindly. See [CALIBRATE.md](../CALIBRATE.md).

## Categories

| Category | What to cut | v0 `expected_level` |
| --- | --- | --- |
| **`crosstalk`** | Two+ people talking over each other (priority) | **`rising`** — stacking *detection* is v1; v0 heat only |
| `calm` | One steady voice, quiet room, TED-style talk | `calm` |
| `rising` | Energy climbing — leaning in, getting louder | `rising` |
| `hot` | Raised voices, the room is clearly hot | `hot` |
| `silence_or_music` | Hold music, dead air (**trap**) | usually `calm` — must not always be `hot` |
| `laughter_applause` | A laugh or clap in a calm stretch (**trap**) | usually `calm` if the burst is brief |

`expected_level` is only `calm` | `rising` | `hot` (the LED). `category` is extra scorecard context.

YouTube / TED **files are loud** (masters near 0 dBFS). That is **not** the same as live headphone volume. Use `madlight calibrate --normalize` (the default) on files. The live monitor path stays **absolute**.

## Local manifest (gitignored media)

```bash
# your Omarchy cuts — example schema (keep wavs out of git):
# path,expected_level,category
# ted_calm.wav,calm,calm
# overlap.wav,rising,crosstalk
# shout.wav,hot,hot

madlight calibrate --manifest samples/manifest.csv
```

A committed template is [manifest.example.csv](manifest.example.csv). Copy to `manifest.csv` and point `path` at your wavs.

## Synthetic stand-ins (CI)

No real meetings in git. Tiny WAVs are generated from `tests/fixtures/manifest.json` (`synth` field), including **`crosstalk`** (sum of two modulated tones):

```bash
madlight calibrate --manifest tests/fixtures/manifest.json
```

Kinds: `silence`, `calm`, `rising`, `hot`, `music_steady`, `laughter_burst`, `crosstalk`, `loud_master_calm`, `hot_master_vc` (turn-taking, expected calm), `hot_master_overlap` (talk-over in the same hot-master domain, expected rising — score with `--no-normalize`).
