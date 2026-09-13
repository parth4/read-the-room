"""Local prefs + thumbs-up/down log. No cloud, no audio on disk."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from madlight.heat import HeatConfig, HeatLevel, HeatSample

PREFS_NAME = "prefs.json"
FEEDBACK_NAME = "feedback.jsonl"
NUDGE_AFTER = 5
NUDGE_LESS = 1.08
NUDGE_MORE = 0.93
RISING_RMS_RANGE = (0.03, 0.22)
HOT_RMS_RANGE = (0.10, 0.45)

# Higher = more sensitive = lower RMS thresholds.
SENSITIVITY_PRESETS: dict[str, float] = {
    "lower": 0.75,
    "default": 1.0,
    "higher": 1.35,
}


def config_dir() -> Path:
    override = os.environ.get("MADLIGHT_CONFIG_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(root) / "madlight"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "madlight"
    return Path.home() / ".config" / "madlight"


def prefs_path(root: Path | None = None) -> Path:
    return (root or config_dir()) / PREFS_NAME


def feedback_path(root: Path | None = None) -> Path:
    return (root or config_dir()) / FEEDBACK_NAME


@dataclass
class Prefs:
    rising_rms: float | None = None
    hot_rms: float | None = None
    rising_slope: float | None = None
    sensitivity: float = 1.0
    down_too_hot: int = 0
    down_too_cold: int = 0
    show_band_meters: bool = False

    def sensitivity_name(self) -> str:
        best = "default"
        best_d = abs(self.sensitivity - 1.0)
        for name, value in SENSITIVITY_PRESETS.items():
            d = abs(self.sensitivity - value)
            if d < best_d:
                best, best_d = name, d
        return best


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def load_prefs(root: Path | None = None) -> Prefs:
    path = prefs_path(root)
    if not path.is_file():
        return Prefs()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Prefs()
    if not isinstance(data, dict):
        return Prefs()
    return Prefs(
        rising_rms=_opt_float(data.get("rising_rms")),
        hot_rms=_opt_float(data.get("hot_rms")),
        rising_slope=_opt_float(data.get("rising_slope")),
        sensitivity=float(data.get("sensitivity") or 1.0),
        down_too_hot=int(data.get("down_too_hot") or 0),
        down_too_cold=int(data.get("down_too_cold") or 0),
        show_band_meters=bool(data.get("show_band_meters", False)),
    )


def save_prefs(prefs: Prefs, root: Path | None = None) -> Path:
    path = prefs_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(prefs), indent=2) + "\n", encoding="utf-8")
    return path


def apply_prefs(cfg: HeatConfig, prefs: Prefs) -> HeatConfig:
    updates: dict[str, float] = {}
    if prefs.rising_rms is not None:
        updates["rising_rms"] = prefs.rising_rms
    if prefs.hot_rms is not None:
        updates["hot_rms"] = prefs.hot_rms
    if prefs.rising_slope is not None:
        updates["rising_slope"] = prefs.rising_slope
    return replace(cfg, **updates) if updates else cfg


def set_sensitivity(prefs: Prefs, name: str, base: HeatConfig | None = None) -> Prefs:
    key = name if name in SENSITIVITY_PRESETS else "default"
    sensitivity = SENSITIVITY_PRESETS[key]
    cfg = base or HeatConfig()
    scale = 1.0 / sensitivity
    return replace(
        prefs,
        sensitivity=sensitivity,
        rising_rms=round(cfg.rising_rms * scale, 4),
        hot_rms=round(cfg.hot_rms * scale, 4),
    )


def note_feedback(
    prefs: Prefs,
    label: str,
    level: HeatLevel,
    *,
    idle: bool = False,
) -> tuple[Prefs, bool]:
    """Count thumbs-down; after N of the same kind, nudge thresholds.

    Down on rising/hot → too sensitive. Down on calm/idle → not sensitive enough.
    Thumbs-up only logs (caller writes JSONL); counters stay put.
    """
    if label != "down":
        return prefs, False
    too_hot = (not idle) and level in {HeatLevel.RISING, HeatLevel.HOT}
    if too_hot:
        nxt = replace(prefs, down_too_hot=prefs.down_too_hot + 1, down_too_cold=0)
        if nxt.down_too_hot >= NUDGE_AFTER:
            return _nudge(nxt, less_sensitive=True), True
        return nxt, False
    nxt = replace(prefs, down_too_cold=prefs.down_too_cold + 1, down_too_hot=0)
    if nxt.down_too_cold >= NUDGE_AFTER:
        return _nudge(nxt, less_sensitive=False), True
    return nxt, False


def _nudge(prefs: Prefs, *, less_sensitive: bool) -> Prefs:
    base = HeatConfig()
    factor = NUDGE_LESS if less_sensitive else NUDGE_MORE
    rising = prefs.rising_rms if prefs.rising_rms is not None else base.rising_rms
    hot = prefs.hot_rms if prefs.hot_rms is not None else base.hot_rms
    return replace(
        prefs,
        rising_rms=round(_clip(rising * factor, *RISING_RMS_RANGE), 4),
        hot_rms=round(_clip(hot * factor, *HOT_RMS_RANGE), 4),
        down_too_hot=0,
        down_too_cold=0,
    )


def append_feedback(
    label: str,
    *,
    sample: HeatSample | None,
    listening: bool,
    idle: bool,
    level: HeatLevel,
    extra: dict[str, Any] | None = None,
    root: Path | None = None,
) -> Path:
    path = feedback_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "listening": listening,
        "idle": idle,
        "level": str(level),
        "rms": None if sample is None else sample.rms,
        "slope": None if sample is None else sample.slope,
        "db_fs": None if sample is None else sample.db_fs,
        "fill": None if sample is None else sample.fill,
        "crest": None if sample is None else sample.crest,
        "cv": None if sample is None else sample.cv,
    }
    if extra:
        row.update(extra)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return path


def _opt_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
