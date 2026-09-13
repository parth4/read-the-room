"""Rolling RMS + slope + density → calm / rising / hot.

Energy only. Not emotion, not speech content, not faces.

Density (fill + crest): calm turn-taking speech is peaky with gaps
(high crest). Talk-over / heated stretch is fuller (high fill, lower
crest, some modulation). Steady music is full but flat (no modulation)
so it stays out of the density path.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

# Frequency-band activity (loopback mix). Not speaker IDs.
LANE_EDGES_HZ: tuple[float, float, float, float] = (80.0, 400.0, 2000.0, 8000.0)
LANE_LABELS: tuple[str, str, str] = ("low", "mid", "high")


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
    rising_slope: float = 0.07
    drop_margin: float = 0.015
    silence_rms: float = 0.008
    # Density path (talk-over / heated room vs peaky monologue).
    density_fill: float = 0.85
    density_crest_max: float = 2.0
    density_cv_min: float = 0.25

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
    fill: float = 0.0
    crest: float = 0.0
    cv: float = 0.0


def _mono(samples: np.ndarray) -> np.ndarray:
    x = np.asarray(samples, dtype=np.float64)
    if x.size == 0:
        return np.asarray([], dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=-1)
    return np.ravel(x)


def block_rms(samples: np.ndarray) -> float:
    """RMS of one block. Stereo is downmixed to mono first."""
    x = _mono(samples)
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(x))))


def db_fs(rms: float) -> float:
    return 20.0 * float(np.log10(max(rms, 1e-12)))


def is_idle(rms: float, floor: float | None = None) -> bool:
    """Sustained near-silence: smoothed RMS below the heat silence floor.

    Used by the LED to paint dark grey instead of calm-green. Does not
    change classify_heat() — silence is still CALM in the classifier.
    """
    cut = HeatConfig().silence_rms if floor is None else float(floor)
    return float(rms) < cut


def activity_lanes(
    samples: np.ndarray,
    sample_rate: int = 16_000,
    edges: tuple[float, ...] = LANE_EDGES_HZ,
) -> tuple[float, ...]:
    """Per-band RMS of the mix via a tiny rFFT split (low / mid / high).

    Honest local stand-in for concurrent activity — **not** diarization
    and not “Person 1/2/3”. Stereo is downmixed first (same as heat).
    """
    x = _mono(samples)
    n_bands = max(0, len(edges) - 1)
    empty = tuple(0.0 for _ in range(n_bands))
    if x.size < 16 or n_bands < 1 or sample_rate <= 0:
        return empty
    n = int(x.size)
    spec = np.fft.rfft(x * np.hanning(n))
    freqs = np.fft.rfftfreq(n, d=1.0 / float(sample_rate))
    bands: list[float] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (freqs >= float(lo)) & (freqs < float(hi))
        part = np.zeros_like(spec)
        if np.any(mask):
            part[mask] = spec[mask]
        y = np.fft.irfft(part, n=n)
        bands.append(float(np.sqrt(np.mean(np.square(y)))))
    return tuple(bands)


def classify_heat(
    rms: float,
    slope: float,
    current: HeatLevel,
    cfg: HeatConfig,
    *,
    fill: float = 0.0,
    crest: float = 0.0,
    cv: float = 0.0,
) -> HeatLevel:
    """Map smoothed RMS + slope + density to heat, with hysteresis."""
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
    climbing = slope >= slope_cut and rms >= cfg.silence_rms
    # Density: continuous/modulated energy (crosstalk), not peaky monologue,
    # not flat music (cv ~ 0).
    dense = (
        fill >= cfg.density_fill
        and 0.0 < crest <= cfg.density_crest_max
        and cv >= cfg.density_cv_min
        and rms >= cfg.silence_rms
    )
    # Absolute loud alone is NOT rising (that false-fired calm TED).
    # Climb or dense talk-over is.
    if climbing or dense:
        return HeatLevel.RISING
    if in_heat and rms >= rms_cut:
        return HeatLevel.RISING
    return HeatLevel.CALM


class HeatClassifier:
    """Rolling RMS buffer → smoothed energy, slope, density, heat level."""

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
        fill, crest, cv = self.density()
        self._level = classify_heat(
            smoothed,
            slope,
            self._level,
            self.config,
            fill=fill,
            crest=crest,
            cv=cv,
        )
        return HeatSample(
            level=self._level,
            rms=smoothed,
            slope=slope,
            db_fs=db_fs(smoothed),
            fill=fill,
            crest=crest,
            cv=cv,
        )

    def smoothed_rms(self) -> float:
        if not self._rms:
            return 0.0
        recent = min(len(self._rms), self.config.slope_blocks)
        chunk = list(self._rms)[-recent:]
        return float(sum(chunk) / len(chunk))

    def density(self) -> tuple[float, float, float]:
        """Return (fill, crest, cv) over the rolling window."""
        if len(self._rms) < 4:
            return 0.0, 0.0, 0.0
        vals = list(self._rms)
        arr = np.asarray(vals, dtype=np.float64)
        fill = float(np.mean(arr >= self.config.silence_rms))
        p50 = float(np.median(arr))
        p95 = float(np.percentile(arr, 95))
        crest = p95 / max(p50, 1e-6)
        mean = float(np.mean(arr))
        cv = float(np.std(arr) / max(mean, 1e-6))
        return fill, float(crest), cv

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
