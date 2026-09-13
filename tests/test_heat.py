"""Heat classifier tests — synthetic energy only, no microphone."""

from __future__ import annotations

import numpy as np
import pytest

from madlight.calibrate import classify_audio
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
from madlight.synth import render_synth


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


def test_loud_steady_is_hot() -> None:
    assert classify_heat(0.30, 0.0, HeatLevel.CALM, CFG) is HeatLevel.HOT


def test_medium_energy_without_slope_stays_calm() -> None:
    # Absolute medium loudness alone is not heat (calm monologue peaks).
    assert classify_heat(0.12, 0.0, HeatLevel.CALM, CFG) is HeatLevel.CALM


def test_density_crosstalk_is_rising() -> None:
    assert (
        classify_heat(0.10, 0.0, HeatLevel.CALM, CFG, fill=0.85, crest=1.8, cv=0.6)
        is HeatLevel.RISING
    )


def test_density_needs_rising_rms_not_silence_floor() -> None:
    """Loud-but-steady / hot-loopback speech used to enter rising via
    density AND rms >= silence_rms (0.008). Normal VC talk must not.
    """
    mid = (CFG.silence_rms + CFG.rising_rms) / 2.0
    assert CFG.silence_rms < mid < CFG.rising_rms
    assert (
        classify_heat(mid, 0.0, HeatLevel.CALM, CFG, fill=0.95, crest=1.5, cv=0.45)
        is HeatLevel.CALM
    )


def test_peaky_monologue_density_stays_calm() -> None:
    assert (
        classify_heat(0.05, 0.0, HeatLevel.CALM, CFG, fill=0.76, crest=4.5, cv=1.1)
        is HeatLevel.CALM
    )


def test_flat_music_density_stays_calm() -> None:
    assert (
        classify_heat(0.08, 0.0, HeatLevel.CALM, CFG, fill=1.0, crest=1.0, cv=0.0)
        is HeatLevel.CALM
    )


def test_quiet_but_climbing_slope_is_rising() -> None:
    # Below rising_rms, above silence, steep slope.
    assert classify_heat(0.03, 0.16, HeatLevel.CALM, CFG) is HeatLevel.RISING


def test_slope_in_silence_stays_calm() -> None:
    assert classify_heat(0.001, 0.5, HeatLevel.CALM, CFG) is HeatLevel.CALM


def test_hot_hysteresis_holds_then_releases() -> None:
    held = classify_heat(0.210, 0.0, HeatLevel.HOT, CFG)
    assert held is HeatLevel.HOT  # 0.22 - 0.015 = 0.205 hold
    dropped = classify_heat(0.10, 0.0, HeatLevel.HOT, CFG)
    assert dropped is HeatLevel.RISING
    calm = classify_heat(0.02, 0.0, HeatLevel.RISING, CFG)
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
    level = _feed(clf, [0.30] * 20)
    assert level is HeatLevel.HOT


def test_classifier_ramp_reports_rising_before_hot() -> None:
    clf = HeatClassifier(CFG)
    _feed(clf, [0.01] * 8)
    start, end, n = 0.01, 0.20, 48
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
    assert sample.level is not HeatLevel.HOT


def test_brief_climb_spike_stays_calm() -> None:
    """One emphatic word (~0.3 s climb) must not flip yellow."""
    clf = HeatClassifier(CFG)
    _feed(clf, [0.01] * 12)
    spike = [0.02 + 0.02 * i for i in range(6)]  # 0.3 s
    level = _feed(clf, spike + [0.012] * 8)
    assert level is HeatLevel.CALM


def test_sustained_climb_becomes_rising() -> None:
    clf = HeatClassifier(CFG)
    _feed(clf, [0.01] * 12)
    # ~2 s of steep climb, well above rise_dwell_seconds.
    ramp = [0.015 + 0.004 * i for i in range(40)]
    sample = None
    first_rising: int | None = None
    for i, rms in enumerate(ramp):
        sample = clf.push_rms(rms)
        if first_rising is None and sample.level is HeatLevel.RISING:
            first_rising = i
    assert sample is not None
    assert sample.level is HeatLevel.RISING
    assert first_rising is not None
    assert first_rising * CFG.block_ms >= 800


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


def test_classifier_push_block_matches_push_rms() -> None:
    clf_a = HeatClassifier(CFG)
    clf_b = HeatClassifier(CFG)
    block = np.full(CFG.block_frames, 0.25, dtype=np.float64)
    a = clf_a.push_block(block)
    b = clf_b.push_rms(block_rms(block))
    assert a.level == b.level
    assert a.rms == pytest.approx(b.rms)


def test_classifier_dense_stream_is_rising() -> None:
    """Low-crest continuous modulated energy → rising (crosstalk-like)."""
    clf = HeatClassifier(CFG)
    # Alternate mild levels around a floor — dense, not peaky.
    sample = None
    for i in range(40):
        # stronger modulation so cv clears density_cv_min
        sample = clf.push_rms(0.08 + (0.07 if i % 2 == 0 else 0.0))
    assert sample is not None
    assert sample.crest <= CFG.density_crest_max
    assert sample.level is HeatLevel.RISING


def test_classifier_peaky_stream_stays_calm() -> None:
    """Sparse peaks with gaps → calm (monologue-like)."""
    clf = HeatClassifier(CFG)
    sample = None
    pattern = [0.002] * 6 + [0.12] + [0.002] * 6 + [0.10]
    for _ in range(4):
        for rms in pattern:
            sample = clf.push_rms(rms)
    assert sample is not None
    assert sample.crest > CFG.density_crest_max or sample.level is HeatLevel.CALM


def test_loud_steady_monologue_does_not_trip_density_via_silence_floor() -> None:
    """Compressed monologue above silence, below rising_rms stays calm.

    This is the hot-loopback false yellow: fill/crest/cv match talk-over
    because the AGC floor is above silence_rms, but energy is not rising.
    """
    clf = HeatClassifier(CFG)
    sample = None
    first_heat_s: float | None = None
    for i in range(80):
        sample = clf.push_rms(0.030 + (0.040 if i % 2 == 0 else 0.0))
        if first_heat_s is None and sample.level is not HeatLevel.CALM:
            first_heat_s = i * CFG.block_ms / 1000.0
    assert sample is not None
    assert sample.rms < CFG.rising_rms
    assert sample.fill >= CFG.density_fill
    assert 0.0 < sample.crest <= CFG.density_crest_max
    assert sample.cv >= CFG.density_cv_min
    assert first_heat_s is None
    assert sample.level is HeatLevel.CALM


def test_hot_master_vc_early_seconds_stay_calm() -> None:
    """Hot-master 2–5 person turn-taking (peak≈0.997) stays calm after warmup.

    Documented live failure: calm→rising at ~2.55 s on a near-full-scale
    Teams-style mix. Density must not fire on the elevated floor alone.
    """
    audio = render_synth("hot_master_vc", sr=CFG.sample_rate)
    assert float(np.max(np.abs(audio))) == pytest.approx(0.997, abs=0.002)
    clf = HeatClassifier(CFG)
    n = CFG.block_frames
    levels: list[HeatLevel] = []
    for i in range(0, audio.size - n + 1, n):
        levels.append(clf.push_block(audio[i : i + n]).level)
    warmup = CFG.slope_blocks
    early = levels[warmup : warmup + int(4.0 * 1000 / CFG.block_ms)]
    assert early
    calm_frac = sum(lv is HeatLevel.CALM for lv in early) / len(early)
    assert calm_frac >= 0.90
    assert HeatLevel.HOT not in early


def test_hot_master_overlap_is_rising_not_hot() -> None:
    """Same master domain, overlapping voices → rising (talk-over), not red."""
    audio = render_synth("hot_master_overlap", sr=CFG.sample_rate)
    score = classify_audio(audio, CFG.sample_rate, CFG, normalize=False)
    assert score.predicted is HeatLevel.RISING
    assert score.counts.get("hot", 0) == 0
