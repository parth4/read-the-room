from __future__ import annotations

import subprocess
import sys
import time


def test_module_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "madlite", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Meeting Atmosphere Dial" in proc.stdout
    assert "--list-sources" in proc.stdout


def test_list_sources_does_not_crash_without_pulse() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "madlite", "--list-sources"],
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
        [sys.executable, "-m", "madlite", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "madlite" in proc.stdout
