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
    "loud_monologue",
    "emphatic_word",
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


def _two_voices(
    n: int,
    sr: int,
    *,
    f1: float = 180.0,
    f2: float = 265.0,
    m1: float = 3.2,
    m2: float = 5.0,
    a1: float = 0.62,
    a2: float = 0.62,
    stagger: float = 0.07,
    gap_hop: float | None = None,
) -> np.ndarray:
    """Two AM-modulated tones — talk-over stand-in (not diarization)."""
    t = np.arange(n, dtype=np.float64) / sr
    v1 = np.sin(2.0 * np.pi * f1 * t) * (a1 + (1.0 - a1) * np.sin(2.0 * np.pi * m1 * t))
    v2 = np.zeros(n, dtype=np.float64)
    d = int(stagger * sr)
    if d < n:
        t2 = np.arange(n - d, dtype=np.float64) / sr
        v2[d:] = np.sin(2.0 * np.pi * f2 * t2) * (
            a2 + (1.0 - a2) * np.sin(2.0 * np.pi * m2 * t2)
        )
    x = v1 + v2
    if gap_hop:
        hop = int(gap_hop * sr)
        mute = int(0.06 * sr)
        for i0 in range(hop, n, hop):
            x[i0 : i0 + mute] *= 0.15
    return x.astype(np.float32)


def _loud_monologue(sr: int, seconds: float = 2.4) -> np.ndarray:
    """One loud voice with syllable gaps — must stay calm (not 'mad')."""
    n = int(seconds * sr)
    x = np.zeros(n, dtype=np.float64)
    hop = int(0.22 * sr)
    dur = int(0.09 * sr)
    for i0 in range(int(0.08 * sr), n - dur, hop):
        x[i0 : i0 + dur] = _tone(dur, sr, 175.0, 0.92)
    return x.astype(np.float32)


def _emphatic_word(sr: int) -> np.ndarray:
    """One short loud syllable in a quiet bed — must not flip yellow."""
    quiet = _tone(int(0.8 * sr), sr, 165.0, 0.03)
    word = _tone(int(0.28 * sr), sr, 190.0, 0.95)
    tail = _tone(int(0.9 * sr), sr, 165.0, 0.03)
    return np.concatenate([quiet, word, tail]).astype(np.float32)


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
        # Milder talk-over: second voice quieter, a few gaps. Expected rising.
        n = int(3.2 * sr)
        return _peakish(_two_voices(n, sr, a1=0.70, a2=0.38, gap_hop=0.42))
    if kind == "hot":
        # Continuous dual talk-over (no gaps) — sustained escalation.
        n = int(3.0 * sr)
        dense = _two_voices(n, sr, a1=0.70, a2=0.70, m1=4.4, m2=6.1, stagger=0.02)
        return _peakish(np.clip(dense, -1.2, 1.2))
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
        # Two overlapping voices (priority fixture). Expected heat = rising.
        n = int(2.4 * sr)
        return _peakish(_two_voices(n, sr, a1=0.68, a2=0.40, gap_hop=0.45))
    if kind == "loud_monologue":
        return _peakish(_loud_monologue(sr))
    if kind == "emphatic_word":
        return _peakish(_emphatic_word(sr))
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
