"""Rolling RMS + short-term slope → calm / rising / hot.

Energy only. Not emotion, not speech content, not faces.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

class HeatLevel(StrEnum):
    CALM = "calm"
    RISING = "rising"
    HOT = "hot"


@dataclass(frozen=True)
class HeatConfig:
    """Tunable thresholds. RMS is linear amplitude in 0..1 (float audio)."""

    sample_rate: int = 16_000
    block_ms: int = 50
    window_seconds: float = 2.0
    slope_seconds: float = 0.6
    rising_rms: float = 0.045
    hot_rms: float = 0.11
    rising_slope: float = 0.035
    drop_margin: float = 0.015
    silence_rms: float = 0.008

    @property
    def block_frames(self) -> int:
        return max(1, int(self.sample_rate * self.block_ms / 1000))

    @property
    def window_blocks(self) -> int:
        return max(2, int(self.window_seconds * 1000 / self.block_ms))

    @property
    def slope_blocks(self) -> int:
        return max(2, int(self.slope_seconds * 1000 / self.block_ms))


@dataclass(frozen=True)
class HeatSample:
    level: HeatLevel
    rms: float
    slope: float
    db_fs: float


def block_rms(samples: np.ndarray) -> float:
    """RMS of one block. Stereo is downmixed to mono first."""
    x = np.asarray(samples, dtype=np.float64)
    if x.size == 0:
        return 0.0
    if x.ndim > 1:
        x = x.mean(axis=-1)
    x = np.ravel(x)
    return float(np.sqrt(np.mean(np.square(x))))


def db_fs(rms: float) -> float:
    return 20.0 * float(np.log10(max(rms, 1e-12)))


def classify_heat(
    rms: float,
    slope: float,
    current: HeatLevel,
    cfg: HeatConfig,
) -> HeatLevel:
    """Map smoothed RMS + slope to a heat level, with hysteresis."""
    hot_enter, hot_hold = cfg.hot_rms, cfg.hot_rms - cfg.drop_margin
    rise_enter, rise_hold = cfg.rising_rms, cfg.rising_rms - cfg.drop_margin
    slope_enter = cfg.rising_slope
    slope_hold = cfg.rising_slope * 0.4

    hot_cut = hot_hold if current is HeatLevel.HOT else hot_enter
    if rms >= hot_cut:
        return HeatLevel.HOT

    in_heat = current is not HeatLevel.CALM
    rms_cut = rise_hold if in_heat else rise_enter
    slope_cut = slope_hold if current is HeatLevel.RISING else slope_enter
    loud_enough = rms >= rms_cut
    climbing = slope >= slope_cut and rms >= cfg.silence_rms
    if loud_enough or climbing:
        return HeatLevel.RISING
    return HeatLevel.CALM


class HeatClassifier:
    """Rolling RMS buffer → smoothed energy, slope, and heat level."""

    def __init__(self, config: HeatConfig | None = None) -> None:
        self.config = config or HeatConfig()
        self._rms = deque(maxlen=self.config.window_blocks)
        self._level = HeatLevel.CALM

    @property
    def level(self) -> HeatLevel:
        return self._level

    def reset(self) -> None:
        self._rms.clear()
        self._level = HeatLevel.CALM

    def push_block(self, samples: np.ndarray) -> HeatSample:
        return self.push_rms(block_rms(samples))

    def push_rms(self, rms: float) -> HeatSample:
        self._rms.append(float(max(0.0, rms)))
        smoothed = self.smoothed_rms()
        slope = self.slope_per_second()
        self._level = classify_heat(smoothed, slope, self._level, self.config)
        return HeatSample(
            level=self._level,
            rms=smoothed,
            slope=slope,
            db_fs=db_fs(smoothed),
        )

    def smoothed_rms(self) -> float:
        if not self._rms:
            return 0.0
        recent = min(len(self._rms), self.config.slope_blocks)
        chunk = list(self._rms)[-recent:]
        return float(sum(chunk) / len(chunk))

    def slope_per_second(self) -> float:
        if len(self._rms) < 4:
            return 0.0
        n = min(self.config.slope_blocks, len(self._rms) // 2)
        values = list(self._rms)
        older = values[-2 * n : -n]
        newer = values[-n:]
        dt = n * self.config.block_ms / 1000.0
        if dt <= 0:
            return 0.0
        return (sum(newer) / n - sum(older) / n) / dt
