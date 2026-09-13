"""Local prefs + feedback log — no audio, no network."""

from __future__ import annotations

from madlight.heat import HeatConfig, HeatLevel, HeatSample
from madlight.prefs import (
    NUDGE_AFTER,
    Prefs,
    apply_prefs,
    append_feedback,
    config_dir,
    load_prefs,
    note_feedback,
    save_prefs,
    set_sensitivity,
)


def test_config_dir_honors_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MADLIGHT_CONFIG_DIR", str(tmp_path / "ml"))
    assert config_dir() == tmp_path / "ml"


def test_prefs_roundtrip(tmp_path) -> None:
    prefs = Prefs(rising_rms=0.07, hot_rms=0.20, sensitivity=1.35)
    save_prefs(prefs, tmp_path)
    loaded = load_prefs(tmp_path)
    assert loaded.rising_rms == 0.07
    assert loaded.hot_rms == 0.20
    assert loaded.sensitivity_name() == "higher"


def test_missing_prefs_are_defaults(tmp_path) -> None:
    loaded = load_prefs(tmp_path)
    assert loaded.rising_rms is None
    cfg = apply_prefs(HeatConfig(), loaded)
    assert cfg.rising_rms == HeatConfig().rising_rms


def test_set_sensitivity_scales_thresholds() -> None:
    base = HeatConfig()
    higher = set_sensitivity(Prefs(), "higher", base)
    lower = set_sensitivity(Prefs(), "lower", base)
    assert higher.rising_rms < base.rising_rms < lower.rising_rms
    assert higher.hot_rms < base.hot_rms < lower.hot_rms
    cfg = apply_prefs(base, higher)
    assert cfg.rising_rms == higher.rising_rms


def test_feedback_jsonl_appends(tmp_path) -> None:
    sample = HeatSample(
        level=HeatLevel.RISING,
        rms=0.09,
        slope=0.15,
        db_fs=-21.0,
        fill=0.9,
        crest=1.6,
        cv=0.4,
    )
    path = append_feedback(
        "down",
        sample=sample,
        listening=True,
        idle=False,
        level=HeatLevel.RISING,
        extra={"rising_rms": 0.08},
        root=tmp_path,
    )
    append_feedback(
        "up",
        sample=None,
        listening=True,
        idle=True,
        level=HeatLevel.CALM,
        root=tmp_path,
    )
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert '"label": "down"' in lines[0]
    assert '"fill": 0.9' in lines[0]
    assert '"label": "up"' in lines[1]


def test_nudge_after_repeated_downs() -> None:
    prefs = Prefs(rising_rms=0.08, hot_rms=0.22)
    nudged = False
    for _ in range(NUDGE_AFTER - 1):
        prefs, nudged = note_feedback(prefs, "down", HeatLevel.RISING, idle=False)
        assert not nudged
    prefs, nudged = note_feedback(prefs, "down", HeatLevel.RISING, idle=False)
    assert nudged
    assert prefs.rising_rms is not None and prefs.rising_rms > 0.08
    assert prefs.down_too_hot == 0

    prefs = Prefs(rising_rms=0.08, hot_rms=0.22)
    for _ in range(NUDGE_AFTER):
        prefs, nudged = note_feedback(prefs, "down", HeatLevel.CALM, idle=True)
    assert nudged
    assert prefs.rising_rms is not None and prefs.rising_rms < 0.08
    prefs, nudged = note_feedback(prefs, "up", HeatLevel.CALM, idle=True)
    assert not nudged
