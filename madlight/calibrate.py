"""Offline accuracy critic + simple threshold search. Local only. Not neural."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import wave
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from madlight.heat import HeatClassifier, HeatConfig, HeatLevel
from madlight.synth import SYNTH_KINDS, write_kind

LEVELS = (HeatLevel.CALM, HeatLevel.RISING, HeatLevel.HOT)


@dataclass(frozen=True)
class ClipSpec:
    path: Path
    expected: HeatLevel
    category: str = ""
    synth: str = ""


@dataclass(frozen=True)
class ClipScore:
    spec: ClipSpec
    predicted: HeatLevel
    max_rms: float
    mean_rms: float
    counts: dict[str, int]

    @property
    def ok(self) -> bool:
        return self.predicted is self.spec.expected


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    """Decode a PCM WAV via stdlib wave (float32 mono)."""
    try:
        import soundfile as sf  # optional
    except ImportError:
        sf = None
    if sf is not None:
        data, sr = sf.read(str(path), always_2d=False)
        x = np.asarray(data, dtype=np.float32)
        if x.ndim > 1:
            x = x.mean(axis=1)
        return x, int(sr)

    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        width = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width == 2:
        ints = np.frombuffer(raw, dtype="<i2")
        x = ints.astype(np.float32) / 32768.0
    elif width == 4:
        ints = np.frombuffer(raw, dtype="<i4")
        x = ints.astype(np.float32) / 2147483648.0
    elif width == 1:
        ints = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        x = (ints - 128.0) / 128.0
    else:
        raise ValueError(f"{path}: unsupported sample width {width}")
    if nch > 1:
        x = x.reshape(-1, nch).mean(axis=1)
    return x, int(sr)


def _resample(x: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or x.size == 0:
        return x
    n_out = max(1, int(round(x.size * dst_sr / src_sr)))
    xp = np.linspace(0.0, 1.0, x.size, endpoint=False)
    fp = np.linspace(0.0, 1.0, n_out, endpoint=False)
    return np.interp(fp, xp, x).astype(np.float32)


def classify_audio(samples: np.ndarray, sr: int, config: HeatConfig) -> ClipScore:
    """Walk blocks; predicted = majority of post-warmup levels."""
    x = _resample(np.asarray(samples, dtype=np.float32).ravel(), sr, config.sample_rate)
    clf = HeatClassifier(config)
    levels: list[HeatLevel] = []
    rmses: list[float] = []
    n = config.block_frames
    if x.size < n:
        x = np.pad(x, (0, n - x.size))
    for i in range(0, x.size - n + 1, n):
        sample = clf.push_block(x[i : i + n])
        levels.append(sample.level)
        rmses.append(sample.rms)
    warmup = min(len(levels), config.slope_blocks)
    tail = levels[warmup:] or levels
    predicted = Counter(tail).most_common(1)[0][0]
    counts = {lv.value: tail.count(lv) for lv in LEVELS}
    dummy = ClipSpec(path=Path("."), expected=HeatLevel.CALM)
    return ClipScore(
        spec=dummy,
        predicted=predicted,
        max_rms=max(rmses) if rmses else 0.0,
        mean_rms=float(sum(rmses) / len(rmses)) if rmses else 0.0,
        counts=counts,
    )


def classify_file(spec: ClipSpec, config: HeatConfig) -> ClipScore:
    audio, sr = load_wav(spec.path)
    raw = classify_audio(audio, sr, config)
    return ClipScore(
        spec=spec,
        predicted=raw.predicted,
        max_rms=raw.max_rms,
        mean_rms=raw.mean_rms,
        counts=raw.counts,
    )


def _parse_level(text: str) -> HeatLevel:
    try:
        return HeatLevel(text.strip().lower())
    except ValueError as exc:
        raise ValueError(f"expected_level must be calm|rising|hot, got {text!r}") from exc


def load_manifest(path: Path) -> list[ClipSpec]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]]
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
    elif path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("JSON manifest must be an array of objects")
        rows = data
    specs: list[ClipSpec] = []
    for row in rows:
        rel = row.get("path") or row.get("file")
        if not rel:
            raise ValueError(f"manifest row missing path: {row}")
        expected = _parse_level(str(row.get("expected_level") or row.get("expected")))
        category = str(row.get("category") or "")
        synth = str(row.get("synth") or "")
        specs.append(
            ClipSpec(
                path=(path.parent / rel).resolve() if not Path(rel).is_absolute() else Path(rel),
                expected=expected,
                category=category,
                synth=synth,
            )
        )
    return specs


def ensure_synth_clip(spec: ClipSpec, sr: int) -> ClipSpec:
    if spec.synth:
        if spec.synth not in SYNTH_KINDS:
            raise ValueError(f"unknown synth {spec.synth!r}; want {SYNTH_KINDS}")
        write_kind(spec.path, spec.synth, sr=sr)
        return spec
    if spec.path.exists():
        return spec
    raise FileNotFoundError(
        f"missing clip {spec.path} (set synth= one of {SYNTH_KINDS} to generate)"
    )


def score_clips(specs: Iterable[ClipSpec], config: HeatConfig) -> list[ClipScore]:
    out: list[ClipScore] = []
    for spec in specs:
        spec = ensure_synth_clip(spec, sr=config.sample_rate)
        out.append(classify_file(spec, config))
    return out


def accuracy(scores: list[ClipScore]) -> float:
    if not scores:
        return 0.0
    return sum(1 for s in scores if s.ok) / len(scores)


def confusion(scores: list[ClipScore]) -> dict[str, dict[str, int]]:
    table = {e.value: {p.value: 0 for p in LEVELS} for e in LEVELS}
    for s in scores:
        table[s.spec.expected.value][s.predicted.value] += 1
    return table


def format_report(scores: list[ClipScore], config: HeatConfig) -> str:
    lines = [
        "Mad Light calibrate — offline critic (not neural, not cloud)",
        f"thresholds: rising_rms={config.rising_rms}  hot_rms={config.hot_rms}  "
        f"rising_slope={config.rising_slope}",
        "",
        f"{'ok':<3}  {'expected':<8} {'predicted':<9} {'max_rms':>7}  clip",
    ]
    for s in scores:
        mark = "✓" if s.ok else "✗"
        name = s.spec.path.name
        extra = f" [{s.spec.category}]" if s.spec.category else ""
        lines.append(
            f"{mark:<3}  {s.spec.expected.value:<8} {s.predicted.value:<9} "
            f"{s.max_rms:7.3f}  {name}{extra}"
        )
    acc = accuracy(scores)
    lines.append("")
    lines.append(f"accuracy  {acc:.0%}  ({sum(1 for s in scores if s.ok)}/{len(scores)})")
    lines.append("confusion (rows=expected, cols=predicted):")
    header = "         " + "".join(f"{lv.value:>8}" for lv in LEVELS)
    lines.append(header)
    table = confusion(scores)
    for exp in LEVELS:
        cells = "".join(f"{table[exp.value][pred.value]:>8}" for pred in LEVELS)
        lines.append(f"{exp.value:<8}{cells}")
    traps = [s for s in scores if s.spec.category in {"silence_or_music", "laughter_applause"}]
    if traps:
        hot_traps = sum(1 for s in traps if s.predicted is HeatLevel.HOT)
        lines.append(
            f"traps called hot: {hot_traps}/{len(traps)}  "
            "(music/laughter should rarely be hot)"
        )
    return "\n".join(lines)


def _grid() -> list[HeatConfig]:
    base = HeatConfig()
    rising_rms = (0.030, 0.045, 0.060, 0.080)
    hot_rms = (0.090, 0.110, 0.140, 0.180)
    slopes = (0.020, 0.035, 0.050)
    out: list[HeatConfig] = []
    for rr in rising_rms:
        for hr in hot_rms:
            if rr >= hr:
                continue
            for sl in slopes:
                out.append(replace(base, rising_rms=rr, hot_rms=hr, rising_slope=sl))
    return out


def propose(specs: list[ClipSpec], start: HeatConfig) -> tuple[HeatConfig, float]:
    """Grid search. Maximize accuracy; break ties toward defaults, fewer trap-hots."""
    labeled = [ensure_synth_clip(s, sr=start.sample_rate) for s in specs]

    def key(cfg: HeatConfig) -> tuple:
        scores = score_clips(labeled, cfg)
        acc = accuracy(scores)
        trap_hot = sum(
            1
            for s in scores
            if s.spec.category in {"silence_or_music", "laughter_applause"}
            and s.predicted is HeatLevel.HOT
        )
        drift = (
            abs(cfg.rising_rms - start.rising_rms)
            + abs(cfg.hot_rms - start.hot_rms)
            + abs(cfg.rising_slope - start.rising_slope)
        )
        return (acc, -trap_hot, -drift)

    best = max([start, *_grid()], key=key)
    return best, accuracy(score_clips(labeled, best))


def format_flags(config: HeatConfig) -> str:
    return (
        f"--rising-rms {config.rising_rms} "
        f"--hot-rms {config.hot_rms} "
        f"--rising-slope {config.rising_slope}"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="madlight calibrate",
        description=(
            "Score labeled clips against the heat classifier and optionally "
            "propose threshold flags. Local grid search — not training."
        ),
    )
    p.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="JSON / JSONL / CSV with path, expected_level, optional category, synth",
    )
    p.add_argument("--propose", action="store_true", help="grid-search thresholds")
    p.add_argument("--rising-rms", type=float, default=None)
    p.add_argument("--hot-rms", type=float, default=None)
    p.add_argument("--rising-slope", type=float, default=None)
    return p


def config_from_args(args: argparse.Namespace) -> HeatConfig:
    cfg = HeatConfig()
    updates = {}
    if args.rising_rms is not None:
        updates["rising_rms"] = args.rising_rms
    if args.hot_rms is not None:
        updates["hot_rms"] = args.hot_rms
    if args.rising_slope is not None:
        updates["rising_slope"] = args.rising_slope
    return replace(cfg, **updates) if updates else cfg


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        specs = load_manifest(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"manifest error: {exc}", file=sys.stderr)
        return 2
    if not specs:
        print("manifest is empty", file=sys.stderr)
        return 2
    config = config_from_args(args)
    try:
        scores = score_clips(specs, config)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(format_report(scores, config))
    if args.propose:
        best, best_acc = propose(specs, config)
        print("")
        print(f"proposed  accuracy={best_acc:.0%}  {format_flags(best)}")
        if best == config:
            print("(same as current thresholds)")
    return 0 if accuracy(scores) == 1.0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
