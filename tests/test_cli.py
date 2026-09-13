from __future__ import annotations

import subprocess
import sys


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


def test_version() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "madlite", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "madlite" in proc.stdout
