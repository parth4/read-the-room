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
    # Defaults sized for hot loopback / loud meeting masters (see README).
    # Linux-quiet headphone mixes can lower these via --rising-rms / --hot-rms.
    rising_rms: float = 0.08
    hot_rms: float = 0.22
    rising_slope: float = 0.14
    drop_margin: float = 0.015
    silence_rms: float = 0.008
    # Density path (talk-over / heated room vs peaky monologue).
    density_fill: float = 0.85
    density_crest_max: float = 2.0
    density_cv_min: float = 0.25
    # Climb must hold before calm→rising (one emphatic word is not yellow).
    # Density already integrates over window_seconds — only a short confirm.
    rise_dwell_seconds: float = 1.2
    density_dwell_seconds: float = 0.15
    hot_dwell_seconds: float = 0.45
    # Card meters: slower than PR #6 (stride 3 / lane EMA 0.16).
    # Lower EMA alpha = heavier history = the strip eases instead of ticking.
    meter_stride: int = 6
    lane_ema: float = 0.08
    wave_ema: float = 0.12

    @property
    def block_frames(self) -> int:
        return max(1, int(self.sample_rate * self.block_ms / 1000))

    @property
    def window_blocks(self) -> int:
        return max(2, int(self.window_seconds * 1000 / self.block_ms))

    @property
    def slope_blocks(self) -> int:
        return max(2, int(self.slope_seconds * 1000 / self.block_ms))

    @property
    def rise_dwell_blocks(self) -> int:
        return max(1, int(round(self.rise_dwell_seconds * 1000 / self.block_ms)))

    @property
    def density_dwell_blocks(self) -> int:
        return max(1, int(round(self.density_dwell_seconds * 1000 / self.block_ms)))

    @property
    def hot_dwell_blocks(self) -> int:
        return max(1, int(round(self.hot_dwell_seconds * 1000 / self.block_ms)))


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


def _level_rank(level: HeatLevel) -> int:
    if level is HeatLevel.HOT:
        return 2
    if level is HeatLevel.RISING:
        return 1
    return 0


def rise_triggers(
    rms: float,
    slope: float,
    current: HeatLevel,
    cfg: HeatConfig,
    *,
    fill: float = 0.0,
    crest: float = 0.0,
    cv: float = 0.0,
) -> tuple[bool, bool]:
    """Return (climbing, dense) using the same cuts as classify_heat."""
    slope_cut = cfg.rising_slope * 0.4 if current is HeatLevel.RISING else cfg.rising_slope
    climbing = slope >= slope_cut and rms >= cfg.silence_rms
    dense = (
        fill >= cfg.density_fill
        and 0.0 < crest <= cfg.density_crest_max
        and cv >= cfg.density_cv_min
        and rms >= cfg.rising_rms
    )
    return climbing, dense


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
    """Map smoothed RMS + slope + density to heat, with hysteresis.

    Instantaneous candidate only. HeatClassifier applies dwell before a
    promotion becomes the displayed level.
    """
    hot_enter, hot_hold = cfg.hot_rms, cfg.hot_rms - cfg.drop_margin
    rise_enter, rise_hold = cfg.rising_rms, cfg.rising_rms - cfg.drop_margin

    hot_cut = hot_hold if current is HeatLevel.HOT else hot_enter
    if rms >= hot_cut:
        return HeatLevel.HOT

    in_heat = current is not HeatLevel.CALM
    rms_cut = rise_hold if in_heat else rise_enter
    climbing, dense = rise_triggers(
        rms, slope, current, cfg, fill=fill, crest=crest, cv=cv
    )
    # Absolute loud alone is NOT rising (that false-fired calm TED).
    # Climb or dense talk-over is.
    if climbing or dense:
        return HeatLevel.RISING
    if in_heat and rms >= rms_cut:
        return HeatLevel.RISING
    return HeatLevel.CALM


def ema(prev: float, new: float, alpha: float) -> float:
    a = max(0.0, min(1.0, float(alpha)))
    return (1.0 - a) * float(prev) + a * float(new)


class MeterSmoother:
    """Slow the card meters: EMA the incoming RMS, one bar every N blocks, EMA lanes."""

    def __init__(
        self,
        *,
        bars: int = 28,
        stride: int = 6,
        lane_alpha: float = 0.08,
        wave_alpha: float = 0.12,
    ) -> None:
        self.bars = max(1, bars)
        self.stride = max(1, stride)
        self.lane_alpha = float(lane_alpha)
        self.wave_alpha = float(wave_alpha)
        self.wave = [0.0] * self.bars
        self.lanes: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._smooth = 0.0
        self._acc: list[float] = []

    def reset(self) -> None:
        self.wave = [0.0] * self.bars
        self.lanes = (0.0, 0.0, 0.0)
        self._smooth = 0.0
        self._acc = []

    def push(
        self, rms: float, lanes: tuple[float, ...]
    ) -> tuple[list[float], tuple[float, float, float]]:
        self._smooth = ema(self._smooth, float(max(0.0, rms)), self.wave_alpha)
        self._acc.append(self._smooth)
        if len(self._acc) >= self.stride:
            avg = sum(self._acc) / len(self._acc)
            self._acc.clear()
            self.wave = self.wave[1:] + [avg]
        incoming = (tuple(float(v) for v in lanes) + (0.0, 0.0, 0.0))[:3]
        self.lanes = (
            ema(self.lanes[0], incoming[0], self.lane_alpha),
            ema(self.lanes[1], incoming[1], self.lane_alpha),
            ema(self.lanes[2], incoming[2], self.lane_alpha),
        )
        return list(self.wave), self.lanes


class HeatClassifier:
    """Rolling RMS buffer → smoothed energy, slope, density, heat level."""

    def __init__(self, config: HeatConfig | None = None) -> None:
        self.config = config or HeatConfig()
        self._rms = deque(maxlen=self.config.window_blocks)
        self._level = HeatLevel.CALM
        self._up_hold = 0

    @property
    def level(self) -> HeatLevel:
        return self._level

    def reset(self) -> None:
        self._rms.clear()
        self._level = HeatLevel.CALM
        self._up_hold = 0

    def push_block(self, samples: np.ndarray) -> HeatSample:
        return self.push_rms(block_rms(samples))

    def _apply_dwell(
        self,
        candidate: HeatLevel,
        *,
        rms: float,
        slope: float,
        fill: float,
        crest: float,
        cv: float,
    ) -> HeatLevel:
        if _level_rank(candidate) <= _level_rank(self._level):
            self._up_hold = 0
            return candidate
        climbing, dense = rise_triggers(
            rms, slope, self._level, self.config, fill=fill, crest=crest, cv=cv
        )
        if candidate is HeatLevel.HOT:
            need = self.config.hot_dwell_blocks
        elif climbing:
            need = self.config.rise_dwell_blocks
        else:
            need = self.config.density_dwell_blocks
        self._up_hold += 1
        if self._up_hold >= need:
            self._up_hold = 0
            return candidate
        return self._level

    def push_rms(self, rms: float) -> HeatSample:
        self._rms.append(float(max(0.0, rms)))
        smoothed = self.smoothed_rms()
        slope = self.slope_per_second()
        fill, crest, cv = self.density()
        candidate = classify_heat(
            smoothed,
            slope,
            self._level,
            self.config,
            fill=fill,
            crest=crest,
            cv=cv,
        )
        self._level = self._apply_dwell(
            candidate, rms=smoothed, slope=slope, fill=fill, crest=crest, cv=cv
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
