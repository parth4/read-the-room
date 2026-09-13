"""Tiny synthetic meeting-ish clips for the offline critic. No real audio."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from madlight.heat import HeatConfig

SYNTH_KINDS = (
    "silence",
    "calm",
    "rising",
    "hot",
    "music_steady",
    "laughter_burst",
    "crosstalk",
    "loud_master_calm",
    "hot_master_vc",
    "hot_master_overlap",
)


def _tone(n: int, sr: int, freq: float, amp: float) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    return (amp * np.sin(2.0 * np.pi * freq * t)).astype(np.float32)


def _hot_master_vc_talk(sr: int) -> np.ndarray:
    """Compressed 2–5 person VC talk at near-full-scale peak.

    Gaps sit above ``silence_rms`` (hot-master / AGC floor) so fill≈1, but
    syllable RMS stays in the 0.04–0.07 band — below default ``rising_rms``.
    """
    n = int(6.0 * sr)
    floor = 0.013
    x = np.full(n, floor, dtype=np.float64)
    hop = int(0.18 * sr)
    dur = int(0.08 * sr)
    for i0 in range(0, n - dur, hop):
        x[i0 : i0 + dur] = _tone(dur, sr, 180.0, 0.105)
    # File peak like the documented RFP recording (one loud sample).
    x[int(0.35 * sr)] = 0.997
    return x.astype(np.float32)


def _hot_master_overlap(sr: int) -> np.ndarray:
    """Talk-over in the same hot-master domain — should go rising, not hot."""
    n = int(4.0 * sr)
    t = np.arange(n, dtype=np.float64) / sr
    v1 = np.sin(2.0 * np.pi * 175.0 * t) * (0.11 + 0.09 * np.sin(2.0 * np.pi * 4.2 * t))
    v2 = np.sin(2.0 * np.pi * 255.0 * t) * (0.10 + 0.09 * np.sin(2.0 * np.pi * 5.6 * t))
    x = v1 + v2 + 0.0
    # Soft floor so fill stays high (compressed mix), without flattening cv.
    x = x + 0.012 * np.sign(x + 1e-12)
    peak = float(np.max(np.abs(x))) if x.size else 1.0
    if peak > 0.45:
        x = x * (0.45 / peak)
    x[int(0.2 * sr)] = 0.997
    return x.astype(np.float32)


def _peakish(x: np.ndarray, peak: float = 0.95) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).ravel()
    m = float(np.max(np.abs(x))) if x.size else 0.0
    if m < 1e-9:
        return x
    return (x * (peak / m)).astype(np.float32)


def render_synth(kind: str, sr: int = 16_000) -> np.ndarray:
    """Return float32 mono in [-1, 1]. Lengths stay short (repo-small).

    Non-silence kinds are peaked near full scale (YouTube-master-ish) so
    ``--normalize`` compares crest/density, not file LUFS.
    """
    if kind == "silence":
        return np.zeros(sr, dtype=np.float32)
    if kind == "calm" or kind == "loud_master_calm":
        # Sparse “syllables” at near-full peak — calm room, loud file.
        n = int(1.5 * sr)
        x = np.zeros(n, dtype=np.float32)
        for start in (0.12, 0.42, 0.72, 1.05):
            syll = _tone(int(0.08 * sr), sr, 170.0, 0.95)
            i = int(start * sr)
            x[i : i + syll.size] = syll[: max(0, n - i)]
        return x
    if kind == "rising":
        # Steep climb so peak-normalize still clears rising_slope.
        n = int(2.4 * sr)
        t = np.arange(n, dtype=np.float64) / sr
        amp = np.clip(0.02 + t * 0.70, 0.02, 0.90)
        return _peakish(amp * np.sin(2.0 * np.pi * 220.0 * t))
    if kind == "hot":
        # Flattened / clipped — high RMS-to-peak (dense heat).
        raw = _tone(int(1.2 * sr), sr, 240.0, 1.4)
        return _peakish(np.clip(raw, -0.45, 0.45))
    if kind == "music_steady":
        n = int(1.6 * sr)
        mix = _tone(n, sr, 220.0, 0.55) + _tone(n, sr, 330.0, 0.40)
        return _peakish(mix)
    if kind == "laughter_burst":
        quiet = _tone(int(0.9 * sr), sr, 160.0, 0.04)
        burst = _tone(int(0.12 * sr), sr, 400.0, 0.95)
        tail = _tone(int(0.5 * sr), sr, 160.0, 0.04)
        return _peakish(np.concatenate([quiet, burst, tail]))
    if kind == "crosstalk":
        # Two overlapping voices (priority fixture). v0 expected heat = rising.
        # Saturated enough that peak-normalize still clears rising_rms.
        n = int(1.6 * sr)
        t = np.arange(n, dtype=np.float64) / sr
        v1 = np.sin(2.0 * np.pi * 180.0 * t) * (0.62 + 0.38 * np.sin(2.0 * np.pi * 3.2 * t))
        v2 = np.zeros(n, dtype=np.float64)
        d = int(0.07 * sr)
        t2 = np.arange(n - d, dtype=np.float64) / sr
        v2[d:] = np.sin(2.0 * np.pi * 265.0 * t2) * (
            0.62 + 0.38 * np.sin(2.0 * np.pi * 5.0 * t2)
        )
        return _peakish(np.clip(v1 + v2, -1.15, 1.15))
    if kind == "hot_master_vc":
        # Hot WASAPI / meeting-master turn-taking: file peak ≈ 0.997, elevated
        # floor above silence_rms, speech RMS typically below rising_rms.
        # Early seconds should stay calm; density must not trip on the floor.
        return _hot_master_vc_talk(sr)
    if kind == "hot_master_overlap":
        # Same master domain, two overlapping voices — density + rising_rms.
        return _hot_master_overlap(sr)
    raise ValueError(f"unknown synth kind {kind!r}; want one of {SYNTH_KINDS}")


def write_wav(path: Path, samples: np.ndarray, sr: int = 16_000) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.asarray(samples, dtype=np.float32).ravel()
    pcm = np.clip(x, -1.0, 1.0)
    ints = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(ints.tobytes())


def write_kind(path: Path, kind: str, sr: int = 16_000) -> Path:
    write_wav(path, render_synth(kind, sr=sr), sr=sr)
    return Path(path)


def default_sr() -> int:
    return HeatConfig().sample_rate


def sine_rms(amp: float) -> float:
    return amp / math.sqrt(2.0)
