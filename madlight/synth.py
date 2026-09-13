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
)


def _tone(n: int, sr: int, freq: float, amp: float) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    return (amp * np.sin(2.0 * np.pi * freq * t)).astype(np.float32)


def render_synth(kind: str, sr: int = 16_000) -> np.ndarray:
    """Return float32 mono in [-1, 1]. Lengths stay short (repo-small)."""
    if kind == "silence":
        return np.zeros(sr, dtype=np.float32)
    if kind == "calm":
        # Quiet speech-ish tone — below rising_rms as sine RMS ≈ amp/√2.
        return _tone(int(1.2 * sr), sr, 180.0, 0.010)
    if kind == "rising":
        quiet = _tone(int(0.25 * sr), sr, 220.0, 0.010)
        n_ramp = int(0.5 * sr)
        t = np.arange(n_ramp, dtype=np.float64) / sr
        amps = np.linspace(0.012, 0.072, n_ramp)
        ramp = (amps * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
        hold = _tone(int(1.3 * sr), sr, 220.0, 0.072)
        return np.concatenate([quiet, ramp, hold])
    if kind == "hot":
        return _tone(int(1.2 * sr), sr, 240.0, 0.22)
    if kind == "music_steady":
        # Hold-music-ish: two steady tones at mid energy. Should not always be HOT.
        n = int(1.6 * sr)
        a = _tone(n, sr, 220.0, 0.055)
        b = _tone(n, sr, 330.0, 0.040)
        mix = a + b
        peak = float(np.max(np.abs(mix))) or 1.0
        return (mix / peak * 0.09).astype(np.float32)
    if kind == "laughter_burst":
        # Brief spike in a quiet clip — trap for “max energy = hot”.
        quiet = _tone(int(0.9 * sr), sr, 160.0, 0.008)
        burst = _tone(int(0.12 * sr), sr, 400.0, 0.20)
        tail = _tone(int(0.5 * sr), sr, 160.0, 0.008)
        return np.concatenate([quiet, burst, tail])
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
