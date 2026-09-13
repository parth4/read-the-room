from __future__ import annotations

import subprocess
import sys

from madlight.app import Runtime, _format_line
from madlight.heat import HeatLevel, HeatSample


def test_module_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "madlight", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Meeting Atmosphere Dial" in proc.stdout
    assert "--list-sources" in proc.stdout
    assert "Mad Light" in proc.stdout
    assert "heat pill" not in proc.stdout.lower()


def test_list_sources_does_not_crash_without_pulse() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "madlight", "--list-sources"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode in {0, 1}
    assert "Traceback" not in proc.stderr
    combined = proc.stdout + proc.stderr
    assert "monitor" in combined.lower() or "unavailable" in combined.lower()


def test_version() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "madlight", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "madlight" in proc.stdout


def test_legacy_module_alias() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "madlite", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "madlight" in proc.stdout


def test_format_line_paused_and_idle() -> None:
    rt = Runtime()
    rt.set_listening(False)
    assert "paused" in _format_line(rt)
    rt.set_listening(True)
    rt.idle = True
    rt.sample = HeatSample(level=HeatLevel.CALM, rms=0.002, slope=0.0, db_fs=-54.0)
    assert _format_line(rt).startswith("idle")
    rt.idle = False
    rt.level = HeatLevel.HOT
    rt.sample = HeatSample(level=HeatLevel.HOT, rms=0.2, slope=0.0, db_fs=-14.0)
    assert _format_line(rt).startswith("hot")
