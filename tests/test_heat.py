"""Heat classifier tests — synthetic energy only, no microphone."""

from __future__ import annotations

import numpy as np
import pytest

from madlite.heat import (
    HeatClassifier,
    HeatConfig,
    HeatLevel,
    block_rms,
    classify_heat,
    db_fs,
)


CFG = HeatConfig(
    block_ms=50,
    window_seconds=2.0,
    slope_seconds=0.6,
    rising_rms=0.045,
    hot_rms=0.11,
    rising_slope=0.035,
    drop_margin=0.015,
    silence_rms=0.008,
)


def test_block_rms_silence_and_full_scale() -> None:
    assert block_rms(np.zeros(512)) == pytest.approx(0.0)
    assert block_rms(np.ones(512)) == pytest.approx(1.0)
    assert block_rms(np.full(256, 0.5)) == pytest.approx(0.5)


def test_block_rms_downmixes_stereo() -> None:
    left = np.ones(100)
    right = np.zeros(100)
    stereo = np.stack([left, right], axis=1)
    assert block_rms(stereo) == pytest.approx(0.5)


def test_db_fs_reference_points() -> None:
    assert db_fs(1.0) == pytest.approx(0.0)
    assert db_fs(0.1) == pytest.approx(-20.0)


def test_silence_is_calm() -> None:
    assert classify_heat(0.001, 0.0, HeatLevel.CALM, CFG) is HeatLevel.CALM


def test_loud_steady_is_hot() -> None:
    assert classify_heat(0.20, 0.0, HeatLevel.CALM, CFG) is HeatLevel.HOT


def test_medium_energy_is_rising() -> None:
    assert classify_heat(0.06, 0.0, HeatLevel.CALM, CFG) is HeatLevel.RISING


def test_quiet_but_climbing_slope_is_rising() -> None:
    # Below rising_rms, above silence, steep slope.
    assert classify_heat(0.02, 0.08, HeatLevel.CALM, CFG) is HeatLevel.RISING


def test_slope_in_silence_stays_calm() -> None:
    assert classify_heat(0.001, 0.5, HeatLevel.CALM, CFG) is HeatLevel.CALM


def test_hot_hysteresis_holds_then_releases() -> None:
    held = classify_heat(0.100, 0.0, HeatLevel.HOT, CFG)
    assert held is HeatLevel.HOT  # 0.11 - 0.015 = 0.095 hold
    dropped = classify_heat(0.05, 0.0, HeatLevel.HOT, CFG)
    assert dropped is HeatLevel.RISING
    calm = classify_heat(0.01, 0.0, HeatLevel.RISING, CFG)
    assert calm is HeatLevel.CALM


def _feed(clf: HeatClassifier, values: list[float]) -> HeatLevel:
    sample = None
    for rms in values:
        sample = clf.push_rms(rms)
    assert sample is not None
    return sample.level


def test_classifier_quiet_stream_stays_calm() -> None:
    clf = HeatClassifier(CFG)
    level = _feed(clf, [0.002] * 40)
    assert level is HeatLevel.CALM
    assert clf.smoothed_rms() == pytest.approx(0.002)
    assert clf.slope_per_second() == pytest.approx(0.0)


def test_classifier_step_up_becomes_hot() -> None:
    clf = HeatClassifier(CFG)
    _feed(clf, [0.002] * 20)
    level = _feed(clf, [0.22] * 16)
    assert level is HeatLevel.HOT


def test_classifier_ramp_reports_rising_before_hot() -> None:
    clf = HeatClassifier(CFG)
    _feed(clf, [0.01] * 8)
    start, end, n = 0.01, 0.07, 16
    ramp = [start + (end - start) * i / (n - 1) for i in range(n)]
    sample = None
    saw_rising = False
    for rms in ramp:
        sample = clf.push_rms(rms)
        if sample.level is HeatLevel.RISING:
            saw_rising = True
            break
    assert sample is not None
    assert saw_rising
    assert sample.slope > 0


def test_slope_positive_on_linear_ramp() -> None:
    clf = HeatClassifier(CFG)
    for i in range(24):
        clf.push_rms(0.01 + 0.004 * i)
    assert clf.slope_per_second() > 0.02


def test_classifier_push_block_matches_push_rms() -> None:
    clf_a = HeatClassifier(CFG)
    clf_b = HeatClassifier(CFG)
    block = np.full(CFG.block_frames, 0.25, dtype=np.float64)
    a = clf_a.push_block(block)
    b = clf_b.push_rms(block_rms(block))
    assert a.level == b.level
    assert a.rms == pytest.approx(b.rms)
