"""Lightweight talk-over score from the loopback mix.

Classical DSP only — no speaker ID, no emotion, no ML. Yellow / red
mean *sustained overlap / interrupted turn-taking*, not loudness.

Primary cue: two independent F0 peaks in the speech fundamental band
(two talkers in the mix). Secondary: envelope fill / crest / short-gap
tightening over ~1 s, gated so steady music and held tones stay out.

RMS / slope are *not* computed here. The classifier may use them as a
small room-energy boost after overlap is already present.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Speech F0 band. Harmonics above this are dropped; two talkers show
# as two non-harmonic peaks in this range.
F0_LO_HZ = 80.0
F0_HI_HZ = 400.0
# Merge peaks closer than this (Hz); 100 ms @ 16 kHz ≈ 10 Hz bins.
F0_MERGE_HZ = 25.0
HARMONIC_RATIO_LO = 1.7
HARMONIC_RATIO_HI = 3.3
HARMONIC_SLACK = 0.08
PEAK_REL_THR = 0.22
# Dual-talker maps: 1.15 independents → 0, 2.0 → 1; ratio 0.20 → full.
DUAL_COUNT_LO = 1.15
DUAL_COUNT_SPAN = 0.85
DUAL_RATIO_FULL = 0.20
CREST_FULL = 1.0
# Crest at/above this is peaky monologue (term → 0).
CREST_PEAKY = 2.2
# Mean gap (seconds) that drives tightness to 0. 0.8 s ≈ a relaxed turn.
GAP_RELAX_SECONDS = 0.80
MIN_PEAK = 1e-4

# Blend: dual-F0 is the overlap-first cue; envelope is the fallback when
# the mix is muddy but still stacked.
W_DUAL = 0.70
W_DENSITY = 0.30
W_FILL = 0.45
W_CREST = 0.30
W_TIGHT = 0.25


@dataclass(frozen=True)
class OverlapFeatures:
    """One-window snapshot. All terms are 0..1 except crest / f0s."""

    score: float
    fill: float
    crest: float
    cv: float
    tightness: float
    f0s: float
    f0_ratio: float
    dual: float
    density: float


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _mono(samples: np.ndarray) -> np.ndarray:
    x = np.asarray(samples, dtype=np.float64)
    if x.size == 0:
        return np.asarray([], dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=-1)
    return np.ravel(x)


def independent_f0s(
    samples: np.ndarray,
    sample_rate: int = 16_000,
    *,
    lo_hz: float = F0_LO_HZ,
    hi_hz: float = F0_HI_HZ,
) -> tuple[int, float]:
    """Count non-harmonic F0 peaks and the 2nd/1st magnitude ratio.

    One talker → typically 1 peak (harmonics rejected). Two overlapping
    voices → 2 peaks that are not integer multiples. Silence → (0, 0).
    """
    x = _mono(samples)
    if x.size < 64 or float(np.max(np.abs(x))) < MIN_PEAK:
        return 0, 0.0
    mag = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    freqs = np.fft.rfftfreq(x.size, d=1.0 / float(sample_rate))
    mask = (freqs >= float(lo_hz)) & (freqs < float(hi_hz))
    band_f = freqs[mask]
    band_m = mag[mask]
    if band_m.size < 5:
        return 0, 0.0
    peak = float(np.max(band_m))
    if peak < 1e-9:
        return 0, 0.0
    thr = PEAK_REL_THR * peak
    found: list[tuple[float, float]] = []
    for i in range(1, band_m.size - 1):
        m = float(band_m[i])
        if m >= thr and m > float(band_m[i - 1]) and m > float(band_m[i + 1]):
            found.append((float(band_f[i]), m))
    found.sort(key=lambda p: -p[1])
    indep: list[tuple[float, float]] = []
    for f0, amp in found[:4]:
        harmonic = False
        for g, _a in indep:
            lo, hi = (f0, g) if f0 < g else (g, f0)
            ratio = hi / max(lo, 1e-6)
            nearest = round(ratio)
            if (
                HARMONIC_RATIO_LO <= ratio <= HARMONIC_RATIO_HI
                and abs(ratio - nearest) < HARMONIC_SLACK
            ):
                harmonic = True
                break
            if abs(f0 - g) < F0_MERGE_HZ:
                harmonic = True
                break
        if not harmonic:
            indep.append((f0, amp))
    if not indep:
        return 0, 0.0
    ratio = float(indep[1][1] / indep[0][1]) if len(indep) >= 2 else 0.0
    return len(indep), _clip01(ratio)


def dual_talker_score(mean_f0s: float, mean_ratio: float) -> float:
    """0..1: two independent fundamentals with a real second peak."""
    count_t = _clip01((float(mean_f0s) - DUAL_COUNT_LO) / DUAL_COUNT_SPAN)
    ratio_t = _clip01(float(mean_ratio) / DUAL_RATIO_FULL)
    return count_t * ratio_t


def adaptive_speech_floor(rms: list[float] | np.ndarray, silence_rms: float) -> float:
    """Gate above the AGC / hot-master floor so fill sees real syllables."""
    arr = np.asarray(list(rms), dtype=np.float64)
    if arr.size == 0:
        return float(silence_rms) * 2.0
    p95 = float(np.percentile(arr, 95))
    return max(float(silence_rms) * 2.0, 0.35 * p95)


def envelope_terms(
    rms: list[float] | np.ndarray,
    *,
    silence_rms: float,
    block_ms: int,
    crest_peaky: float = CREST_PEAKY,
) -> tuple[float, float, float, float]:
    """Return (fill, crest, cv, tightness) over the RMS window."""
    arr = np.asarray(list(rms), dtype=np.float64)
    if arr.size < 4:
        return 0.0, 0.0, 0.0, 0.0
    floor = adaptive_speech_floor(arr, silence_rms)
    fill = float(np.mean(arr >= floor))
    p50 = float(np.median(arr))
    p95 = float(np.percentile(arr, 95))
    crest = p95 / max(p50, 1e-6)
    mean = float(np.mean(arr))
    cv = float(np.std(arr) / max(mean, 1e-6))
    active = arr >= floor
    gaps: list[int] = []
    run = 0
    for on in active:
        if not on:
            run += 1
        elif run:
            gaps.append(run)
            run = 0
    if run:
        gaps.append(run)
    if gaps:
        mean_gap_s = float(np.mean(gaps)) * float(block_ms) / 1000.0
        tightness = _clip01(1.0 - mean_gap_s / GAP_RELAX_SECONDS)
    else:
        tightness = 1.0 if fill > 0.7 else 0.0
    return fill, float(crest), cv, tightness


def density_score(
    fill: float,
    crest: float,
    cv: float,
    tightness: float,
    *,
    cv_min: float,
    crest_peaky: float = CREST_PEAKY,
) -> float:
    """Envelope stacking. Zero when the mix is too flat (music / held tone)."""
    if float(cv) < float(cv_min) or float(fill) < 0.15:
        return 0.0
    fill_t = _clip01(fill)
    crest_t = _clip01((float(crest_peaky) - float(crest)) / (crest_peaky - CREST_FULL))
    tight_t = _clip01(tightness)
    return W_FILL * fill_t + W_CREST * crest_t + W_TIGHT * tight_t


def score_overlap(
    *,
    fill: float,
    crest: float,
    cv: float,
    tightness: float,
    mean_f0s: float,
    mean_ratio: float,
    cv_min: float,
    crest_peaky: float = CREST_PEAKY,
) -> OverlapFeatures:
    """Blend dual-F0 (primary) with envelope density (secondary)."""
    dual = dual_talker_score(mean_f0s, mean_ratio)
    if float(fill) < 0.15:
        dual = 0.0
    # Two *steady* tones (hold music, a fifth) look like dual-F0.
    # Real overlap still has some envelope motion. Gate only that flat case
    # — do not zero dual just because cv is a bit low (compressed mix).
    flat_tonal = float(cv) < 0.05 and float(crest) <= 1.15 and float(fill) >= 0.85
    if flat_tonal:
        dual = 0.0
        density = 0.0
        score = 0.0
    else:
        density = density_score(
            fill, crest, cv, tightness, cv_min=cv_min, crest_peaky=crest_peaky
        )
        score = _clip01(W_DUAL * dual + W_DENSITY * density)
    return OverlapFeatures(
        score=score,
        fill=float(fill),
        crest=float(crest),
        cv=float(cv),
        tightness=float(tightness),
        f0s=float(mean_f0s),
        f0_ratio=float(mean_ratio),
        dual=float(dual),
        density=float(density),
    )


def features_from_window(
    rms: list[float] | np.ndarray,
    f0s: list[float] | np.ndarray,
    ratios: list[float] | np.ndarray,
    *,
    silence_rms: float,
    block_ms: int,
    cv_min: float,
    crest_peaky: float = CREST_PEAKY,
) -> OverlapFeatures:
    """Score a rolling window of per-block RMS + F0 cues."""
    fill, crest, cv, tightness = envelope_terms(
        rms, silence_rms=silence_rms, block_ms=block_ms, crest_peaky=crest_peaky
    )
    f0_arr = np.asarray(list(f0s), dtype=np.float64)
    r_arr = np.asarray(list(ratios), dtype=np.float64)
    mean_f0s = float(np.mean(f0_arr)) if f0_arr.size else 0.0
    mean_ratio = float(np.mean(r_arr)) if r_arr.size else 0.0
    return score_overlap(
        fill=fill,
        crest=crest,
        cv=cv,
        tightness=tightness,
        mean_f0s=mean_f0s,
        mean_ratio=mean_ratio,
        cv_min=cv_min,
        crest_peaky=crest_peaky,
    )


def overlap_from_legacy_row(
    fill: float | None,
    crest: float | None,
    cv: float | None,
    *,
    cv_min: float,
    tightness: float = 0.7,
    crest_peaky: float = CREST_PEAKY,
) -> float | None:
    """Reconstruct a density-only score for pre-overlap feedback.jsonl rows."""
    if fill is None or crest is None or cv is None:
        return None
    feat = score_overlap(
        fill=float(fill),
        crest=float(crest),
        cv=float(cv),
        tightness=float(tightness),
        mean_f0s=0.0,
        mean_ratio=0.0,
        cv_min=cv_min,
        crest_peaky=crest_peaky,
    )
    return feat.score
