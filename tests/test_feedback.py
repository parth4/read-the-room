"""Feedback schema + --from-feedback overlap fit — local files only."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from madlight.feedback import (
    SCHEMA,
    apply_fit_to_prefs,
    fit_from_rows,
    format_fit,
    overlap_of_row,
    recalibrate_from_feedback,
)
from madlight.heat import HeatConfig, HeatLevel, HeatSample
from madlight.prefs import (
    FEEDBACK_SCHEMA,
    Prefs,
    append_feedback,
    apply_prefs,
    load_prefs,
    note_feedback,
    NUDGE_AFTER,
)


def test_schema_version_is_documented() -> None:
    assert SCHEMA == 2
    assert FEEDBACK_SCHEMA == SCHEMA


def test_append_feedback_writes_schema_and_overlap(tmp_path: Path) -> None:
    sample = HeatSample(
        level=HeatLevel.RISING,
        rms=0.09,
        slope=0.02,
        db_fs=-21.0,
        overlap=0.61,
        fill=0.9,
        crest=1.6,
        cv=0.4,
        tightness=0.8,
        f0s=1.8,
    )
    path = append_feedback(
        "down",
        sample=sample,
        listening=True,
        idle=False,
        level=HeatLevel.RISING,
        extra={"overlap_rising": 0.48, "overlap_hot": 0.86},
        root=tmp_path,
    )
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["schema"] == 2
    assert row["overlap"] == pytest.approx(0.61)
    assert row["f0s"] == 1.8
    assert row["overlap_rising"] == 0.48
    assert "label" in row and row["label"] == "down"


def test_overlap_of_row_uses_legacy_density_proxy() -> None:
    cfg = HeatConfig()
    assert overlap_of_row({"overlap": 0.55}, cfg) == pytest.approx(0.55)
    proxy = overlap_of_row({"fill": 0.9, "crest": 1.3, "cv": 0.3}, cfg)
    assert proxy is not None and 0.0 <= proxy <= 1.0
    assert overlap_of_row({"label": "down"}, cfg) is None


def test_fit_raises_overlap_after_false_heat() -> None:
    rows = [
        {"label": "down", "level": "rising", "idle": False, "overlap": 0.40},
        {"label": "down", "level": "hot", "idle": False, "overlap": 0.42},
        {"label": "up", "level": "calm", "idle": False, "overlap": 0.38},
    ]
    start = HeatConfig()
    fit = fit_from_rows(rows, start)
    assert fit.n_used == 3
    assert fit.n_false_heat == 2
    assert fit.config.overlap_rising > start.overlap_rising
    text = format_fit(fit)
    assert "overlap_rising" in text
    assert "false_heat=2" in text


def test_fit_lowers_overlap_after_missed_heat() -> None:
    rows = [
        {"label": "down", "level": "calm", "idle": False, "overlap": 0.62},
        {"label": "down", "level": "calm", "idle": True, "overlap": 0.58},
        {"label": "up", "level": "rising", "idle": False, "overlap": 0.70},
    ]
    start = HeatConfig()
    fit = fit_from_rows(rows, start)
    assert fit.n_missed_heat == 2
    assert fit.config.overlap_rising < start.overlap_rising


def test_recalibrate_writes_prefs(tmp_path: Path) -> None:
    sample = HeatSample(
        level=HeatLevel.RISING,
        rms=0.1,
        slope=0.0,
        db_fs=-20.0,
        overlap=0.41,
        fill=0.8,
        crest=1.4,
        cv=0.3,
    )
    for _ in range(4):
        append_feedback(
            "down",
            sample=sample,
            listening=True,
            idle=False,
            level=HeatLevel.RISING,
            root=tmp_path,
        )
    fit = recalibrate_from_feedback(tmp_path, write=True)
    assert fit.n_used >= 4
    prefs = load_prefs(tmp_path)
    assert prefs.overlap_rising == fit.config.overlap_rising
    cfg = apply_prefs(HeatConfig(), prefs)
    assert cfg.overlap_rising == fit.config.overlap_rising


def test_nudge_moves_overlap_thresholds() -> None:
    prefs = Prefs(overlap_rising=0.48, overlap_hot=0.86)
    for _ in range(NUDGE_AFTER):
        prefs, nudged = note_feedback(prefs, "down", HeatLevel.RISING, idle=False)
    assert nudged
    assert prefs.overlap_rising is not None and prefs.overlap_rising > 0.48


def test_from_feedback_cli(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MADLIGHT_CONFIG_DIR", str(tmp_path))
    append_feedback(
        "down",
        sample=HeatSample(
            level=HeatLevel.HOT,
            rms=0.12,
            slope=0.0,
            db_fs=-18.0,
            overlap=0.44,
            fill=0.85,
            crest=1.4,
            cv=0.28,
        ),
        listening=True,
        idle=False,
        level=HeatLevel.HOT,
        root=tmp_path,
    )
    proc = subprocess.run(
        [sys.executable, "-m", "madlight", "calibrate", "--from-feedback", "--write-prefs"],
        check=False,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "MADLIGHT_CONFIG_DIR": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    assert "from-feedback" in proc.stdout
    assert "overlap_rising" in proc.stdout
    assert load_prefs(tmp_path).overlap_rising is not None


def test_recalibrate_alias(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "madlight", "recalibrate"],
        check=False,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "MADLIGHT_CONFIG_DIR": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    assert "from-feedback" in proc.stdout


def test_apply_fit_to_prefs_clears_nudge_counters() -> None:
    fit = fit_from_rows(
        [{"label": "up", "level": "calm", "idle": True, "overlap": 0.2}],
        HeatConfig(),
    )
    prefs = apply_fit_to_prefs(fit, Prefs(down_too_hot=3, down_too_cold=1))
    assert prefs.down_too_hot == 0
    assert prefs.overlap_rising == fit.config.overlap_rising
