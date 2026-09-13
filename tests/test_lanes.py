"""Idle floor and frequency-band activity lanes — synthetic audio only."""

from __future__ import annotations

import numpy as np
import pytest

from madlight.heat import (
    HeatConfig,
    LANE_EDGES_HZ,
    LANE_LABELS,
    activity_lanes,
    is_idle,
)


def _tone(freq: float, sr: int = 16_000, ms: int = 50, amp: float = 0.4) -> np.ndarray:
    n = int(sr * ms / 1000)
    t = np.arange(n, dtype=np.float64) / sr
    return (amp * np.sin(2.0 * np.pi * freq * t)).astype(np.float64)


def test_silence_floor_matches_heat_default() -> None:
    assert HeatConfig().silence_rms == pytest.approx(0.008)
    assert is_idle(0.0)
    assert is_idle(0.007)
    assert not is_idle(0.008)
    assert not is_idle(0.02)


def test_silence_floor_is_overridable() -> None:
    assert is_idle(0.01, floor=0.02)
    assert not is_idle(0.01, floor=0.005)


def test_lane_labels_are_bands_not_people() -> None:
    assert LANE_LABELS == ("low", "mid", "high")
    assert len(LANE_EDGES_HZ) == 4
    joined = " ".join(LANE_LABELS).lower()
    assert "person" not in joined
    assert "speaker" not in joined


def test_empty_and_tiny_blocks_are_zero_lanes() -> None:
    assert activity_lanes(np.array([])) == (0.0, 0.0, 0.0)
    assert activity_lanes(np.zeros(8)) == (0.0, 0.0, 0.0)


def test_low_tone_dominates_low_lane() -> None:
    lo, mid, hi = activity_lanes(_tone(150.0))
    assert lo > mid * 3
    assert lo > hi * 3


def test_mid_tone_dominates_mid_lane() -> None:
    lo, mid, hi = activity_lanes(_tone(800.0))
    assert mid > lo * 3
    assert mid > hi * 3


def test_high_tone_dominates_high_lane() -> None:
    lo, mid, hi = activity_lanes(_tone(3200.0))
    assert hi > lo * 3
    assert hi > mid * 3


def test_activity_lanes_downmix_stereo() -> None:
    n = 800
    left = np.sin(2.0 * np.pi * 150.0 * np.arange(n) / 16_000)
    right = np.zeros(n)
    stereo = np.stack([left, right], axis=1)
    lo_s, _, _ = activity_lanes(stereo)
    lo_m, _, _ = activity_lanes(left * 0.5)
    assert lo_s == pytest.approx(lo_m, rel=0.15)


def test_heat_classifier_defaults() -> None:
    cfg = HeatConfig()
    assert cfg.rising_rms == pytest.approx(0.08)
    assert cfg.hot_rms == pytest.approx(0.22)
    assert cfg.rising_slope == pytest.approx(0.14)
    assert cfg.drop_margin == pytest.approx(0.015)
    assert cfg.silence_rms == pytest.approx(0.008)
    assert cfg.density_fill == pytest.approx(0.85)
    assert cfg.density_crest_max == pytest.approx(2.0)
    assert cfg.density_cv_min == pytest.approx(0.25)
