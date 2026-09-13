from __future__ import annotations

import subprocess
import sys


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
