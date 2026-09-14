"""Local thumbs log: schema, parse, and fit overlap cuts from labeled moments.

Ratings never leave the machine. No audio is stored. This is a grid-free
fit of *his* VC-mix thumbs onto overlap_rising / overlap_hot — not neural
training and not a universal model.

Schema (feedback.jsonl)
-----------------------
One JSON object per line. ``schema`` is 2 for overlap-first rows.
Older lines omit ``schema`` / ``overlap``; the fitter reconstructs a
density-only proxy from ``fill`` / ``crest`` / ``cv`` so those thumbs
still count.

| Field | Type | Meaning |
| --- | --- | --- |
| ``schema`` | int | ``2`` = overlap-first. Omitted on pre-v1 lines. |
| ``ts`` | string | UTC ISO-8601 timestamp. |
| ``label`` | ``up`` \\| ``down`` | Tune + / −. Up = this heat feels right; down = wrong. |
| ``listening`` | bool | Capture was on. |
| ``idle`` | bool | Near-silence (armed grey), not a heat color. |
| ``level`` | ``calm`` \\| ``rising`` \\| ``hot`` | Displayed heat at the tap. |
| ``overlap`` | number \\| null | 0..1 talk-over score (primary). |
| ``rms`` | number \\| null | Smoothed linear RMS (secondary room energy). |
| ``slope`` | number \\| null | RMS per second (secondary). |
| ``db_fs`` | number \\| null | ``20 log10(rms)``. |
| ``fill`` | number \\| null | Adaptive-floor speech fill in the overlap window. |
| ``crest`` | number \\| null | p95 / p50 of block RMS (peaky vs full). |
| ``cv`` | number \\| null | Coefficient of variation (music ≈ 0). |
| ``tightness`` | number \\| null | Short-gap / interruption term 0..1. |
| ``f0s`` | number \\| null | Mean independent F0 count in the window. |
| ``rising_rms`` ``hot_rms`` | number | RMS cuts in force (secondary). |
| ``overlap_rising`` ``overlap_hot`` | number | Overlap cuts in force (primary). |

How a down/up is read
---------------------
- **down** on rising/hot (not idle) → false heat: overlap bar was too low.
- **down** on calm/idle → missed heat: overlap bar was too high.
- **up** on rising/hot → true heat example.
- **up** on calm/idle → true calm example.

``madlight calibrate --from-feedback`` places ``overlap_rising`` between
the high side of “should be calm” and the low side of “should be heat”,
and ``overlap_hot`` from thumbs that named hot vs rising. Prefs are
written only with ``--write-prefs``. The card gear can run the same fit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from madlight.heat import HeatConfig
from madlight.overlap import overlap_from_legacy_row
from madlight.prefs import (
    OVERLAP_HOT_RANGE,
    OVERLAP_RISING_RANGE,
    Prefs,
    feedback_path,
    load_prefs,
    save_prefs,
)

SCHEMA = 2
# Ignore ancient / incomplete lines. Recent VC domain beats a huge mixed pile.
MAX_ROWS = 250


@dataclass(frozen=True)
class FeedbackFit:
    config: HeatConfig
    n_used: int
    n_false_heat: int
    n_missed_heat: int
    n_true_heat: int
    n_true_calm: int
    note: str


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _opt_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def overlap_of_row(row: dict[str, Any], cfg: HeatConfig) -> float | None:
    """Prefer logged overlap; else a density-only proxy from older thumbs."""
    direct = _opt_float(row.get("overlap"))
    if direct is not None:
        return _clip(direct, 0.0, 1.0)
    return overlap_from_legacy_row(
        _opt_float(row.get("fill")),
        _opt_float(row.get("crest")),
        _opt_float(row.get("cv")),
        cv_min=cfg.density_cv_min,
        tightness=float(_opt_float(row.get("tightness")) or 0.7),
        crest_peaky=cfg.density_crest_max,
    )


def load_feedback_rows(root: Path | None = None, *, limit: int = MAX_ROWS) -> list[dict[str, Any]]:
    path = feedback_path(root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    if limit > 0:
        rows = rows[-limit:]
    return rows


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    q = max(0.0, min(1.0, q))
    idx = q * (len(arr) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(arr) - 1)
    frac = idx - lo
    return arr[lo] * (1.0 - frac) + arr[hi] * frac


def _bags(rows: list[dict[str, Any]], cfg: HeatConfig) -> dict[str, list[float]]:
    bags: dict[str, list[float]] = {
        "false_heat": [],
        "missed_heat": [],
        "true_heat": [],
        "true_hot": [],
        "true_calm": [],
        "false_hot": [],
    }
    for row in rows:
        ov = overlap_of_row(row, cfg)
        if ov is None:
            continue
        label = str(row.get("label") or "").strip().lower()
        level = str(row.get("level") or "").strip().lower()
        idle = bool(row.get("idle", False))
        heat = (not idle) and level in {"rising", "hot"}
        if label == "down" and heat:
            bags["false_heat"].append(ov)
            if level == "hot":
                bags["false_hot"].append(ov)
        elif label == "down" and (idle or level == "calm"):
            bags["missed_heat"].append(ov)
        elif label == "up" and heat:
            bags["true_heat"].append(ov)
            if level == "hot":
                bags["true_hot"].append(ov)
        elif label == "up" and (idle or level == "calm"):
            bags["true_calm"].append(ov)
    return bags


def fit_from_rows(
    rows: list[dict[str, Any]],
    start: HeatConfig | None = None,
) -> FeedbackFit:
    """Place overlap cuts from labeled moments. KISS percentile split."""
    cfg = start or HeatConfig()
    bags = _bags(rows, cfg)
    used = (
        len(bags["false_heat"])
        + len(bags["missed_heat"])
        + len(bags["true_heat"])
        + len(bags["true_calm"])
    )
    if used == 0:
        return FeedbackFit(
            config=cfg,
            n_used=0,
            n_false_heat=0,
            n_missed_heat=0,
            n_true_heat=0,
            n_true_calm=0,
            note="no usable thumbs (need overlap or fill/crest/cv on the line)",
        )

    rising = cfg.overlap_rising
    hot = cfg.overlap_hot

    should_calm = bags["false_heat"] + bags["true_calm"]
    should_heat = bags["true_heat"] + bags["missed_heat"]
    low = _percentile(should_calm, 0.75)
    high = _percentile(should_heat, 0.25)

    if low is not None and high is not None and high > low + 0.03:
        rising = (low + high) / 2.0
        note = "split calm-vs-heat overlap clouds"
    elif low is not None and (high is None or high <= low):
        # False heat / true calm sit at or above the would-be heat cloud:
        # raise the bar (less sensitive) — his VC mix was over-firing.
        rising = max(rising, low + 0.04)
        if len(bags["false_heat"]) > len(bags["missed_heat"]):
            rising = max(rising, cfg.overlap_rising * 1.08)
        note = "raised overlap_rising from false-heat / true-calm thumbs"
    elif high is not None:
        rising = min(rising, high - 0.04)
        if len(bags["missed_heat"]) > len(bags["false_heat"]):
            rising = min(rising, cfg.overlap_rising * 0.93)
        note = "lowered overlap_rising from missed-heat / true-heat thumbs"
    else:
        note = "not enough contrast; kept overlap_rising"

    # Hot: thumbs that named hot, vs heat that should stay yellow.
    hot_cloud = bags["true_hot"]
    not_hot = [v for v in bags["true_heat"] if v not in bags["true_hot"]]
    not_hot += bags["false_hot"]
    hot_lo = _percentile(not_hot, 0.75) if not_hot else None
    hot_hi = _percentile(hot_cloud, 0.25) if hot_cloud else None
    if hot_lo is not None and hot_hi is not None and hot_hi > hot_lo + 0.03:
        hot = (hot_lo + hot_hi) / 2.0
    elif bags["false_hot"] and not bags["true_hot"]:
        hot = max(hot, (_percentile(bags["false_hot"], 0.75) or hot) + 0.04)
    elif hot_hi is not None:
        hot = min(hot, max(rising + 0.12, hot_hi))

    rising = _clip(rising, *OVERLAP_RISING_RANGE)
    hot = _clip(max(hot, rising + 0.10), *OVERLAP_HOT_RANGE)
    fitted = replace(
        cfg,
        overlap_rising=round(rising, 3),
        overlap_hot=round(hot, 3),
    )
    return FeedbackFit(
        config=fitted,
        n_used=used,
        n_false_heat=len(bags["false_heat"]),
        n_missed_heat=len(bags["missed_heat"]),
        n_true_heat=len(bags["true_heat"]),
        n_true_calm=len(bags["true_calm"]),
        note=note,
    )


def apply_fit_to_prefs(fit: FeedbackFit, prefs: Prefs) -> Prefs:
    return replace(
        prefs,
        overlap_rising=fit.config.overlap_rising,
        overlap_hot=fit.config.overlap_hot,
        down_too_hot=0,
        down_too_cold=0,
    )


def recalibrate_from_feedback(
    root: Path | None = None,
    *,
    write: bool = True,
    start: HeatConfig | None = None,
) -> FeedbackFit:
    """Read JSONL, fit overlap cuts, optionally persist prefs."""
    prefs = load_prefs(root)
    rows = load_feedback_rows(root)
    fit = fit_from_rows(rows, start or HeatConfig())
    if write and fit.n_used:
        save_prefs(apply_fit_to_prefs(fit, prefs), root)
    return fit


def format_fit(fit: FeedbackFit) -> str:
    cfg = fit.config
    return (
        f"from-feedback  used={fit.n_used}  "
        f"false_heat={fit.n_false_heat} missed={fit.n_missed_heat} "
        f"true_heat={fit.n_true_heat} true_calm={fit.n_true_calm}\n"
        f"  overlap_rising={cfg.overlap_rising}  overlap_hot={cfg.overlap_hot}\n"
        f"  {fit.note}"
    )
