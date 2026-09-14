# Sample clips (local)

**Priority class: crosstalk** — multiple people talking over each other (stacking). That is the finding that started this folder.

On a local Omarchy box you may already have **yt-dlp cuts** here (gitignored `*.wav`) plus `manifest.csv`. **Do not commit those blobs.**

The critic reads a **manifest**, not the directory blindly. See [CALIBRATE.md](../CALIBRATE.md).

## Categories

| Category | What to cut | `expected_level` |
| --- | --- | --- |
| **`crosstalk`** | Two+ people talking over each other (priority) | **`rising`** or **`hot`** if the pile-on holds |
| `calm` | One steady voice, quiet room, TED-style talk — even if the file is loud | `calm` |
| `rising` | Mild / starting talk-over | `rising` |
| `hot` | Sustained pile-on, the room is clearly stacked | `hot` |
| `silence_or_music` | Hold music, dead air (**trap**) | usually `calm` — must not always be `hot` |
| `laughter_applause` | A laugh, clap, or one emphatic word in a calm stretch (**trap**) | usually `calm` if the burst is brief |

`expected_level` is only `calm` | `rising` | `hot` (the LED). `category` is extra scorecard context.

YouTube / TED **files are loud** (masters near 0 dBFS). That is **not** the same as live headphone volume. Overlap-first heat cares about **two talkers in the mix**, not LUFS. Use `madlight calibrate --normalize` (the default) on files. The live monitor path stays **absolute**.

## Local manifest (gitignored media)

```bash
# your Omarchy cuts — example schema (keep wavs out of git):
# path,expected_level,category
# ted_calm.wav,calm,calm
# overlap.wav,rising,crosstalk
# pileon.wav,hot,crosstalk

madlight calibrate --manifest samples/manifest.csv
```

A committed template is [manifest.example.csv](manifest.example.csv). Copy to `manifest.csv` and point `path` at your wavs.

## Synthetic stand-ins (CI)

No real meetings in git. Tiny WAVs are generated from `tests/fixtures/manifest.json` (`synth` field):

```bash
madlight calibrate --manifest tests/fixtures/manifest.json
```

Kinds: `silence`, `calm`, `rising` (mild two-voice), `hot` (dense two-voice), `music_steady`, `laughter_burst`, `crosstalk`, `loud_master_calm`, `loud_monologue` (expected calm), `emphatic_word` (expected calm), `hot_master_vc` (turn-taking, expected calm), `hot_master_overlap` (talk-over in the same hot-master domain, expected hot).
