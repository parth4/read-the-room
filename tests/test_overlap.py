"""Overlap-first heat — synthetic audio only, no microphone."""

from __future__ import annotations

import numpy as np
import pytest

from madlight.calibrate import classify_audio
from madlight.heat import HeatClassifier, HeatConfig, HeatLevel, classify_heat, rise_triggers
from madlight.overlap import (
    dual_talker_score,
    independent_f0s,
    score_overlap,
)
from madlight.synth import render_synth

CFG = HeatConfig()


def _tone(n: int, sr: int, freq: float, amp: float) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    return (amp * np.sin(2.0 * np.pi * freq * t)).astype(np.float64)


def test_independent_f0s_one_tone() -> None:
    sr = 16_000
    x = _tone(sr // 10, sr, 180.0, 0.4)  # 100 ms
    count, ratio = independent_f0s(x, sr)
    assert count == 1
    assert ratio == pytest.approx(0.0)


def test_independent_f0s_two_talkers() -> None:
    sr = 16_000
    n = sr // 10
    x = _tone(n, sr, 175.0, 0.35) + _tone(n, sr, 255.0, 0.32)
    count, ratio = independent_f0s(x, sr)
    assert count >= 2
    assert ratio >= 0.2


def test_independent_f0s_silence() -> None:
    assert independent_f0s(np.zeros(800), 16_000) == (0, 0.0)


def test_harmonic_of_one_voice_is_not_two_talkers() -> None:
    sr = 16_000
    n = sr // 10
    x = _tone(n, sr, 120.0, 0.4) + _tone(n, sr, 240.0, 0.25)
    count, _ratio = independent_f0s(x, sr)
    assert count == 1


def test_dual_talker_score_needs_count_and_ratio() -> None:
    assert dual_talker_score(1.0, 0.5) == pytest.approx(0.0)
    assert dual_talker_score(2.0, 0.0) == pytest.approx(0.0)
    assert dual_talker_score(2.0, 0.25) == pytest.approx(1.0)


def test_flat_music_overlap_is_zero() -> None:
    feat = score_overlap(
        fill=1.0, crest=1.0, cv=0.0, tightness=1.0, mean_f0s=2.0, mean_ratio=0.7, cv_min=0.10
    )
    assert feat.score == pytest.approx(0.0)


def test_overlap_score_two_talkers_is_high() -> None:
    feat = score_overlap(
        fill=0.9, crest=1.3, cv=0.3, tightness=0.9, mean_f0s=1.9, mean_ratio=0.5, cv_min=0.10
    )
    assert feat.score >= CFG.overlap_rising
    assert feat.dual > 0.5


def test_classify_loud_without_overlap_stays_calm() -> None:
    assert classify_heat(0.30, 0.0, HeatLevel.CALM, CFG, overlap=0.10) is HeatLevel.CALM
    assert classify_heat(0.12, 0.20, HeatLevel.CALM, CFG, overlap=0.10) is HeatLevel.CALM


def test_classify_overlap_is_rising_then_hot() -> None:
    assert classify_heat(0.10, 0.0, HeatLevel.CALM, CFG, overlap=0.60) is HeatLevel.RISING
    assert classify_heat(0.10, 0.0, HeatLevel.RISING, CFG, overlap=0.92) is HeatLevel.HOT


def test_silence_stays_calm_even_with_overlap_ghost() -> None:
    assert classify_heat(0.001, 0.0, HeatLevel.CALM, CFG, overlap=0.90) is HeatLevel.CALM


def test_rise_triggers_are_overlap_not_slope() -> None:
    rising, hot = rise_triggers(0.10, 0.20, HeatLevel.CALM, CFG, overlap=0.10)
    assert rising is False and hot is False
    rising, hot = rise_triggers(0.10, 0.0, HeatLevel.CALM, CFG, overlap=0.60)
    assert rising is True and hot is False


def test_loud_monologue_fixture_stays_calm() -> None:
    audio = render_synth("loud_monologue", sr=CFG.sample_rate)
    score = classify_audio(audio, CFG.sample_rate, CFG, normalize=False)
    assert score.predicted is HeatLevel.CALM
    assert score.counts.get("rising", 0) == 0
    assert score.counts.get("hot", 0) == 0


def test_hot_master_vc_stays_calm() -> None:
    audio = render_synth("hot_master_vc", sr=CFG.sample_rate)
    score = classify_audio(audio, CFG.sample_rate, CFG, normalize=False)
    assert score.predicted is HeatLevel.CALM


def test_overlapping_voices_become_heat() -> None:
    for kind, want in (("crosstalk", HeatLevel.RISING), ("hot", HeatLevel.HOT), ("rising", HeatLevel.RISING)):
        audio = render_synth(kind, sr=CFG.sample_rate)
        score = classify_audio(audio, CFG.sample_rate, CFG, normalize=False)
        assert score.predicted is want, kind


def test_emphatic_word_does_not_flip_yellow() -> None:
    audio = render_synth("emphatic_word", sr=CFG.sample_rate)
    clf = HeatClassifier(CFG)
    n = CFG.block_frames
    saw_heat = False
    for i in range(0, audio.size - n + 1, n):
        if clf.push_block(audio[i : i + n]).level is not HeatLevel.CALM:
            saw_heat = True
            break
    assert saw_heat is False


def test_overlap_dwell_blocks_one_block_spike() -> None:
    clf = HeatClassifier(CFG)
    for i in range(12):
        clf.push_rms(0.08 + (0.03 if i % 2 else 0.0), f0s=1.0, f0_ratio=0.0)
    # Six blocks (~0.3 s) of dual-talker — shorter than rise dwell.
    sample = None
    for i in range(6):
        sample = clf.push_rms(0.10 + (0.05 if i % 2 else 0.0), f0s=2.0, f0_ratio=0.6)
    assert sample is not None
    assert sample.level is HeatLevel.CALM
    for i in range(CFG.rise_dwell_blocks + 8):
        sample = clf.push_rms(0.10 + (0.05 if i % 2 else 0.0), f0s=2.0, f0_ratio=0.6)
    assert sample.level is HeatLevel.RISING


def test_calm_to_hot_steps_through_rising() -> None:
    clf = HeatClassifier(CFG)
    for _ in range(8):
        clf.push_rms(0.02, f0s=0.0, f0_ratio=0.0)
    saw = []
    for i in range(40):
        lv = clf.push_rms(0.12 + (0.06 if i % 2 else 0.0), f0s=2.0, f0_ratio=0.7).level
        if not saw or saw[-1] is not lv:
            saw.append(lv)
    assert HeatLevel.RISING in saw
    assert HeatLevel.HOT in saw
    assert saw.index(HeatLevel.RISING) < saw.index(HeatLevel.HOT)


def test_music_steady_stays_calm() -> None:
    audio = render_synth("music_steady", sr=CFG.sample_rate)
    score = classify_audio(audio, CFG.sample_rate, CFG, normalize=True)
    assert score.predicted is HeatLevel.CALM
