"""Heat classifier tests — synthetic energy / overlap only, no microphone."""

from __future__ import annotations

import numpy as np
import pytest

from madlight.heat import (
    HeatClassifier,
    HeatConfig,
    HeatLevel,
    MeterSmoother,
    block_rms,
    classify_heat,
    db_fs,
    ema,
)

CFG = HeatConfig()


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


def test_loud_steady_without_overlap_is_calm() -> None:
    assert classify_heat(0.30, 0.0, HeatLevel.CALM, CFG, overlap=0.0) is HeatLevel.CALM


def test_medium_energy_without_overlap_stays_calm() -> None:
    assert classify_heat(0.12, 0.0, HeatLevel.CALM, CFG, overlap=0.1) is HeatLevel.CALM


def test_slope_without_overlap_stays_calm() -> None:
    assert classify_heat(0.03, 0.16, HeatLevel.CALM, CFG, overlap=0.1) is HeatLevel.CALM


def test_slope_in_silence_stays_calm() -> None:
    assert classify_heat(0.001, 0.5, HeatLevel.CALM, CFG, overlap=0.9) is HeatLevel.CALM


def test_overlap_hysteresis_holds_then_releases() -> None:
    held = classify_heat(0.10, 0.0, HeatLevel.HOT, CFG, overlap=0.80)
    assert held is HeatLevel.HOT  # 0.86 - 0.08 hold
    dropped = classify_heat(0.10, 0.0, HeatLevel.HOT, CFG, overlap=0.55)
    assert dropped is HeatLevel.RISING
    calm = classify_heat(0.10, 0.0, HeatLevel.RISING, CFG, overlap=0.20)
    assert calm is HeatLevel.CALM


def _feed(clf: HeatClassifier, values: list[float], *, f0s: float = 0.0, ratio: float = 0.0) -> HeatLevel:
    sample = None
    for rms in values:
        sample = clf.push_rms(rms, f0s=f0s, f0_ratio=ratio)
    assert sample is not None
    return sample.level


def test_classifier_quiet_stream_stays_calm() -> None:
    clf = HeatClassifier(CFG)
    level = _feed(clf, [0.002] * 40)
    assert level is HeatLevel.CALM
    assert clf.smoothed_rms() == pytest.approx(0.002)
    assert clf.slope_per_second() == pytest.approx(0.0)


def test_classifier_loud_step_stays_calm() -> None:
    """Loudness alone is not heat — a monologue step must stay green."""
    clf = HeatClassifier(CFG)
    _feed(clf, [0.002] * 20)
    level = _feed(clf, [0.30] * 20)
    assert level is HeatLevel.CALM


def test_brief_overlap_spike_stays_calm() -> None:
    clf = HeatClassifier(CFG)
    _feed(clf, [0.08] * 12, f0s=1.0)
    level = _feed(clf, [0.12] * 6, f0s=2.0, ratio=0.6)
    assert level is HeatLevel.CALM


def test_sustained_overlap_becomes_rising() -> None:
    clf = HeatClassifier(CFG)
    _feed(clf, [0.08] * 12, f0s=1.0)
    sample = None
    first_rising: int | None = None
    for i in range(40):
        # Alternate RMS so CV is speech-like (flat dual tones look like music).
        sample = clf.push_rms(0.10 + (0.05 if i % 2 else 0.0), f0s=2.0, f0_ratio=0.55)
        if first_rising is None and sample.level is HeatLevel.RISING:
            first_rising = i
    assert sample is not None
    assert sample.level in {HeatLevel.RISING, HeatLevel.HOT}
    assert first_rising is not None
    assert first_rising * CFG.block_ms >= 400


def test_meter_smoother_strides_wave_and_emas_lanes() -> None:
    meter = MeterSmoother(bars=8, stride=3, lane_alpha=0.5, wave_alpha=1.0)
    wave, lanes = meter.push(0.09, (0.2, 0.0, 0.0))
    assert wave[-1] == 0.0
    assert lanes[0] == pytest.approx(0.1)
    wave, _ = meter.push(0.09, (0.2, 0.0, 0.0))
    assert wave[-1] == 0.0
    wave, _ = meter.push(0.09, (0.2, 0.0, 0.0))
    assert wave[-1] == pytest.approx(0.09)
    assert ema(0.0, 1.0, 0.25) == pytest.approx(0.25)


def test_meter_defaults_are_slower_than_pr6() -> None:
    cfg = HeatConfig()
    assert cfg.meter_stride >= 6
    assert cfg.lane_ema <= 0.08
    assert cfg.wave_ema <= 0.12
    meter = MeterSmoother()
    assert meter.stride == 6
    assert meter.lane_alpha == pytest.approx(0.08)


def test_slope_positive_on_linear_ramp() -> None:
    clf = HeatClassifier(CFG)
    for i in range(24):
        clf.push_rms(0.01 + 0.004 * i)
    assert clf.slope_per_second() > 0.02


def test_classifier_push_block_matches_push_rms_energy() -> None:
    clf_a = HeatClassifier(CFG)
    clf_b = HeatClassifier(CFG)
    block = np.full(CFG.block_frames, 0.25, dtype=np.float64)
    a = clf_a.push_block(block)
    b = clf_b.push_rms(block_rms(block))
    assert a.rms == pytest.approx(b.rms)
    # A flat tone has no dual-F0; both stay calm.
    assert a.level is HeatLevel.CALM
    assert b.level is HeatLevel.CALM
