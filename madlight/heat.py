"""Overlap-first heat: talk-over → calm / rising / hot.

Not emotion, not speech content, not faces. Yellow / red mean sustained
talk-over or interrupted turn-taking on the local loopback mix. RMS and
slope are secondary room-energy only — they do not promote alone.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from madlight.overlap import (
    CREST_PEAKY,
    OverlapFeatures,
    features_from_window,
    independent_f0s,
)

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
    # Overlap score is computed on this trailing slice of the RMS window.
    overlap_seconds: float = 1.0
    # Two-block (100 ms) F0 analysis — cheap, real-time.
    f0_blocks: int = 2
    # Defaults sized for 2–5 person VC on a hot loopback / loud master.
    # Overlap 0..1; rising / hot are talk-over cuts, not loudness cuts.
    overlap_rising: float = 0.48
    overlap_hot: float = 0.86
    overlap_drop: float = 0.08
    overlap_ema: float = 0.35
    # Room-energy (secondary). May shave the overlap cut once overlap
    # is already present. Never promotes a loud monologue by itself.
    rising_rms: float = 0.08
    hot_rms: float = 0.22
    rising_slope: float = 0.14
    energy_overlap_boost: float = 0.05
    drop_margin: float = 0.015
    silence_rms: float = 0.008
    # Envelope density (talk-over vs peaky monologue / flat music).
    density_fill: float = 0.85
    density_crest_max: float = CREST_PEAKY
    density_cv_min: float = 0.10
    # Climb / overlap must hold so one emphatic word is not yellow.
    rise_dwell_seconds: float = 0.70
    hot_dwell_seconds: float = 0.40
    # Card meters: slower than a raw block meter.
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
    def overlap_blocks(self) -> int:
        return max(4, int(self.overlap_seconds * 1000 / self.block_ms))

    @property
    def rise_dwell_blocks(self) -> int:
        return max(1, int(round(self.rise_dwell_seconds * 1000 / self.block_ms)))

    @property
    def hot_dwell_blocks(self) -> int:
        return max(1, int(round(self.hot_dwell_seconds * 1000 / self.block_ms)))


@dataclass(frozen=True)
class HeatSample:
    level: HeatLevel
    rms: float
    slope: float
    db_fs: float
    overlap: float = 0.0
    fill: float = 0.0
    crest: float = 0.0
    cv: float = 0.0
    tightness: float = 0.0
    f0s: float = 0.0


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


def energy_boost(rms: float, slope: float, overlap: float, cfg: HeatConfig) -> float:
    """Small cut-shave when overlap is already present *and* the room climbs.

    Returns 0 unless overlap agrees — loud monologue does not get a boost.
    """
    if overlap < cfg.overlap_rising * 0.65:
        return 0.0
    if rms < cfg.rising_rms or slope < cfg.rising_slope * 0.5:
        return 0.0
    return float(cfg.energy_overlap_boost)


def rise_triggers(
    rms: float,
    slope: float,
    current: HeatLevel,
    cfg: HeatConfig,
    *,
    overlap: float = 0.0,
) -> tuple[bool, bool]:
    """Return (overlap_rising, overlap_hot) using the same cuts as classify_heat."""
    boost = energy_boost(rms, slope, overlap, cfg)
    rise_cut = cfg.overlap_rising
    hot_cut = cfg.overlap_hot
    if current is HeatLevel.RISING or current is HeatLevel.HOT:
        rise_cut -= cfg.overlap_drop
    if current is HeatLevel.HOT:
        hot_cut -= cfg.overlap_drop
    rise_cut = max(0.0, rise_cut - boost)
    hot_cut = max(0.0, hot_cut - boost)
    if rms < cfg.silence_rms:
        return False, False
    return overlap >= rise_cut, overlap >= hot_cut


def classify_heat(
    rms: float,
    slope: float,
    current: HeatLevel,
    cfg: HeatConfig,
    *,
    overlap: float = 0.0,
    fill: float = 0.0,
    crest: float = 0.0,
    cv: float = 0.0,
) -> HeatLevel:
    """Map overlap (+ optional room-energy boost) to heat, with hysteresis.

    Instantaneous candidate only. HeatClassifier applies dwell before a
    promotion becomes the displayed level.

    ``fill`` / ``crest`` / ``cv`` are accepted for older call sites and
    ignored — pass ``overlap`` (the 0..1 talk-over score).
    """
    del fill, crest, cv
    if rms < cfg.silence_rms:
        return HeatLevel.CALM

    rising, hot = rise_triggers(rms, slope, current, cfg, overlap=overlap)
    if hot:
        return HeatLevel.HOT
    if rising:
        return HeatLevel.RISING

    in_heat = current is not HeatLevel.CALM
    if in_heat and overlap >= (cfg.overlap_rising - cfg.overlap_drop) * 0.7:
        if rms >= cfg.rising_rms - cfg.drop_margin:
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
    """Rolling RMS + F0 → overlap score → heat level with dwell."""

    def __init__(self, config: HeatConfig | None = None) -> None:
        self.config = config or HeatConfig()
        self._rms: deque[float] = deque(maxlen=self.config.window_blocks)
        self._f0s: deque[float] = deque(maxlen=self.config.window_blocks)
        self._ratios: deque[float] = deque(maxlen=self.config.window_blocks)
        self._raw: deque[np.ndarray] = deque(maxlen=max(1, self.config.f0_blocks))
        self._level = HeatLevel.CALM
        self._up_hold = 0
        self._overlap_smooth = 0.0
        self._feat = OverlapFeatures(
            score=0.0,
            fill=0.0,
            crest=0.0,
            cv=0.0,
            tightness=0.0,
            f0s=0.0,
            f0_ratio=0.0,
            dual=0.0,
            density=0.0,
        )

    @property
    def level(self) -> HeatLevel:
        return self._level

    def reset(self) -> None:
        self._rms.clear()
        self._f0s.clear()
        self._ratios.clear()
        self._raw.clear()
        self._level = HeatLevel.CALM
        self._up_hold = 0
        self._overlap_smooth = 0.0
        self._feat = OverlapFeatures(
            score=0.0,
            fill=0.0,
            crest=0.0,
            cv=0.0,
            tightness=0.0,
            f0s=0.0,
            f0_ratio=0.0,
            dual=0.0,
            density=0.0,
        )

    def push_block(self, samples: np.ndarray) -> HeatSample:
        x = _mono(samples)
        self._raw.append(x)
        f0_count, f0_ratio = independent_f0s(
            np.concatenate(list(self._raw)), self.config.sample_rate
        )
        return self.push_rms(block_rms(samples), f0s=float(f0_count), f0_ratio=f0_ratio)

    def _apply_dwell(
        self,
        candidate: HeatLevel,
        *,
        rms: float,
        slope: float,
        overlap: float,
    ) -> HeatLevel:
        if _level_rank(candidate) <= _level_rank(self._level):
            self._up_hold = 0
            return candidate
        # One rank at a time so calm → rising → hot (not a calm→hot skip).
        if _level_rank(candidate) > _level_rank(self._level) + 1:
            candidate = HeatLevel.RISING
        need = (
            self.config.hot_dwell_blocks
            if candidate is HeatLevel.HOT
            else self.config.rise_dwell_blocks
        )
        self._up_hold += 1
        if self._up_hold >= need:
            self._up_hold = 0
            return candidate
        return self._level

    def push_rms(
        self,
        rms: float,
        *,
        f0s: float = 0.0,
        f0_ratio: float = 0.0,
    ) -> HeatSample:
        self._rms.append(float(max(0.0, rms)))
        self._f0s.append(float(max(0.0, f0s)))
        self._ratios.append(float(max(0.0, min(1.0, f0_ratio))))
        feat = self.overlap_features()
        self._overlap_smooth = ema(self._overlap_smooth, feat.score, self.config.overlap_ema)
        self._feat = feat
        smoothed = self.smoothed_rms()
        slope = self.slope_per_second()
        overlap = self._overlap_smooth
        candidate = classify_heat(
            smoothed,
            slope,
            self._level,
            self.config,
            overlap=overlap,
        )
        self._level = self._apply_dwell(
            candidate, rms=smoothed, slope=slope, overlap=overlap
        )
        return HeatSample(
            level=self._level,
            rms=smoothed,
            slope=slope,
            db_fs=db_fs(smoothed),
            overlap=overlap,
            fill=feat.fill,
            crest=feat.crest,
            cv=feat.cv,
            tightness=feat.tightness,
            f0s=feat.f0s,
        )

    def overlap_features(self) -> OverlapFeatures:
        n = min(len(self._rms), self.config.overlap_blocks)
        if n < 4:
            return OverlapFeatures(
                score=0.0,
                fill=0.0,
                crest=0.0,
                cv=0.0,
                tightness=0.0,
                f0s=0.0,
                f0_ratio=0.0,
                dual=0.0,
                density=0.0,
            )
        rms = list(self._rms)[-n:]
        f0s = list(self._f0s)[-n:]
        ratios = list(self._ratios)[-n:]
        return features_from_window(
            rms,
            f0s,
            ratios,
            silence_rms=self.config.silence_rms,
            block_ms=self.config.block_ms,
            cv_min=self.config.density_cv_min,
            crest_peaky=self.config.density_crest_max,
        )

    def smoothed_rms(self) -> float:
        if not self._rms:
            return 0.0
        recent = min(len(self._rms), self.config.slope_blocks)
        chunk = list(self._rms)[-recent:]
        return float(sum(chunk) / len(chunk))

    def density(self) -> tuple[float, float, float]:
        """Return (fill, crest, cv) over the overlap window (legacy tuple)."""
        feat = self._feat
        return feat.fill, feat.crest, feat.cv

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
