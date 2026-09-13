"""Offline critic tests — synthetic energy and tiny generated WAVs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from madlight.calibrate import (
    accuracy,
    classify_audio,
    format_flags,
    format_report,
    load_manifest,
    propose,
    score_clips,
)
from madlight.heat import HeatClassifier, HeatConfig, HeatLevel
from madlight.synth import render_synth, write_kind

CFG = HeatConfig()
FIXTURE_MANIFEST = Path(__file__).parent / "fixtures" / "manifest.json"


def test_manifest_lists_fixture_categories() -> None:
    specs = load_manifest(FIXTURE_MANIFEST)
    cats = {s.category for s in specs}
    assert {"calm", "rising", "hot", "silence_or_music", "laughter_applause", "crosstalk"} <= cats
    assert all(s.synth for s in specs)


def test_energy_order_indices() -> None:
    clf = HeatClassifier(CFG)
    first: dict[HeatLevel, int] = {}
    i = 0
    for rms in [0.004] * 16:
        first.setdefault(clf.push_rms(rms).level, i)
        i += 1
    for rms in [0.02 + 0.004 * k for k in range(14)]:
        first.setdefault(clf.push_rms(rms).level, i)
        i += 1
    for rms in [0.20] * 12:
        first.setdefault(clf.push_rms(rms).level, i)
        i += 1
    assert first[HeatLevel.CALM] < first[HeatLevel.RISING] < first[HeatLevel.HOT]


def test_music_steady_is_not_hot_when_normalized() -> None:
    audio = render_synth("music_steady", sr=CFG.sample_rate)
    score = classify_audio(audio, CFG.sample_rate, CFG, normalize=True)
    assert score.predicted is not HeatLevel.HOT


def test_loud_master_calm_false_hot_without_normalize() -> None:
    audio = render_synth("loud_master_calm", sr=CFG.sample_rate)
    abs_score = classify_audio(audio, CFG.sample_rate, CFG, normalize=False)
    rel_score = classify_audio(audio, CFG.sample_rate, CFG, normalize=True)
    assert abs_score.predicted is HeatLevel.HOT
    assert rel_score.predicted is not HeatLevel.HOT


def test_crosstalk_synth_is_rising_when_normalized() -> None:
    audio = render_synth("crosstalk", sr=CFG.sample_rate)
    score = classify_audio(audio, CFG.sample_rate, CFG, normalize=True)
    assert score.predicted is HeatLevel.RISING


def test_fixture_scorecard_and_cli(tmp_path: Path) -> None:
    specs = load_manifest(FIXTURE_MANIFEST)
    # Generate next to the committed manifest so the documented command works.
    scores = score_clips(specs, CFG, normalize=True)
    report = format_report(scores, CFG, normalize=True)
    assert "accuracy" in report
    assert "confusion" in report
    assert "expected" in report
    assert "peak-normalized" in report
    by_name = {s.spec.path.name: s for s in scores}
    assert by_name["synth_silence.wav"].predicted is HeatLevel.CALM
    assert by_name["synth_rising.wav"].predicted is HeatLevel.RISING
    assert by_name["synth_hot.wav"].predicted is HeatLevel.HOT
    assert by_name["synth_crosstalk.wav"].predicted is HeatLevel.RISING
    assert by_name["synth_loud_master_calm.wav"].predicted is not HeatLevel.HOT
    assert by_name["synth_music_steady.wav"].predicted is not HeatLevel.HOT
    assert by_name["synth_laughter_burst.wav"].predicted is not HeatLevel.HOT

    proc = subprocess.run(
        [sys.executable, "-m", "madlight", "calibrate", "--manifest", str(FIXTURE_MANIFEST)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "accuracy" in proc.stdout
    assert "synth_hot.wav" in proc.stdout
    assert "crosstalk" in proc.stdout
    assert "peak-normalized" in proc.stdout

    abs_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "madlight",
            "calibrate",
            "--manifest",
            str(FIXTURE_MANIFEST),
            "--no-normalize",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert abs_proc.returncode == 0, abs_proc.stderr
    assert "absolute RMS" in abs_proc.stdout


def test_propose_returns_heat_config() -> None:
    specs = load_manifest(FIXTURE_MANIFEST)
    best, acc = propose(specs, CFG)
    assert isinstance(best, HeatConfig)
    assert 0.0 <= acc <= 1.0
    flags = format_flags(best)
    assert "--rising-rms" in flags
    assert "--hot-rms" in flags


def test_module_calibrate_entrypoint(tmp_path: Path) -> None:
    dest = tmp_path / "one.wav"
    write_kind(dest, "hot")
    man = tmp_path / "m.json"
    man.write_text(
        json.dumps([{"path": "one.wav", "expected_level": "hot", "category": "hot"}]),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "madlight.calibrate", "--manifest", str(man)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "hot" in proc.stdout
    assert accuracy(score_clips(load_manifest(man), CFG, normalize=True)) == 1.0


def test_csv_manifest(tmp_path: Path) -> None:
    write_kind(tmp_path / "s.wav", "silence")
    csv_path = tmp_path / "m.csv"
    csv_path.write_text("path,expected_level,category\ns.wav,calm,silence_or_music\n")
    specs = load_manifest(csv_path)
    assert specs[0].expected is HeatLevel.CALM
    assert score_clips(specs, CFG)[0].ok
