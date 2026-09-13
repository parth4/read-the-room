"""Monitor discovery parsers — no live Pulse session required."""

from __future__ import annotations

import numpy as np
import pytest

from madlight.audio import (
    CaptureError,
    DemoCapture,
    MonitorSource,
    discover_monitor,
    parse_pactl_short_sources,
    parse_pactl_sink_monitor,
)
from madlight.heat import HeatClassifier, HeatConfig, HeatLevel, activity_lanes, is_idle


SHORT_SOURCES = """\
0\talsa_output.usb-Headphones.analog-stereo.monitor\tPipeWire\ts32le 2ch 48000Hz\tRUNNING
1\talsa_input.usb-Headphones.analog-mono\tPipeWire\ts32le 1ch 48000Hz\tSUSPENDED
2\talsa_output.pci-0000_00_1f.3.analog-stereo.monitor\tPipeWire\ts32le 2ch 44100Hz\tSUSPENDED
"""

LIST_SINKS = """\
Sink #31
	State: RUNNING
	Name: alsa_output.usb-Headphones.analog-stereo
	Description: USB Headphones
	Monitor Source: alsa_output.usb-Headphones.analog-stereo.monitor
	Mute: no

Sink #54
	State: SUSPENDED
	Name: alsa_output.pci-0000_00_1f.3.analog-stereo
	Description: Built-in Audio
	Monitor Source: alsa_output.pci-0000_00_1f.3.analog-stereo.monitor
	Mute: no
"""


def test_parse_short_sources_skips_empty() -> None:
    names = parse_pactl_short_sources(SHORT_SOURCES)
    assert names[0].endswith(".monitor")
    assert "alsa_input.usb-Headphones.analog-mono" in names
    assert len(names) == 3


def test_parse_sink_monitor_follows_headphone_sink() -> None:
    monitor = parse_pactl_sink_monitor(
        LIST_SINKS, "alsa_output.usb-Headphones.analog-stereo"
    )
    assert monitor == "alsa_output.usb-Headphones.analog-stereo.monitor"


def test_parse_sink_monitor_unknown_sink() -> None:
    assert parse_pactl_sink_monitor(LIST_SINKS, "missing") is None


def test_monitor_source_rejects_plain_mic_name() -> None:
    mic = MonitorSource(
        pulse_name="alsa_input.usb-Headphones.analog-mono",
        label="USB Headphones Analog Mono",
        via="cli",
    )
    assert not mic.looks_like_monitor()
    loop = MonitorSource(
        pulse_name="alsa_output.usb-Headphones.analog-stereo.monitor",
        label="monitor of USB Headphones",
        via="pactl",
    )
    assert loop.looks_like_monitor()


def test_explicit_mic_refused_without_flag() -> None:
    with pytest.raises(CaptureError, match="microphone"):
        discover_monitor("alsa_input.pci-0000_00_1f.3.analog-stereo")


def test_explicit_monitor_allowed() -> None:
    src = discover_monitor("alsa_output.usb-Headphones.analog-stereo.monitor")
    assert src.pulse_name.endswith(".monitor")


def test_demo_capture_cycles_quiet_to_hot() -> None:
    cfg = HeatConfig(block_ms=50, sample_rate=8_000)
    cap = DemoCapture(cfg)
    clf = HeatClassifier(cfg)
    levels: list[HeatLevel] = []
    # 10s loop at 50ms → 200 blocks covers quiet, climb, hot, fade
    for _ in range(200):
        levels.append(clf.push_block(cap.read()).level)
    cap.close()
    assert HeatLevel.CALM in levels
    assert HeatLevel.RISING in levels
    assert HeatLevel.HOT in levels
    # last fade block should be heading down; a quiet stretch exists
    quiet = DemoCapture(cfg)
    first = float(np.max(np.abs(quiet.read())))
    assert first < 0.02


def test_demo_quiet_is_idle_and_lanes_diverge() -> None:
    cfg = HeatConfig(block_ms=50, sample_rate=16_000)
    cap = DemoCapture(cfg)
    quiet = HeatClassifier(cfg).push_block(cap.read())
    assert is_idle(quiet.rms, cfg.silence_rms)

    # Skip the silent head (~2s), then look for mixed-band energy.
    for _ in range(50):
        cap.read()
    peaked = [activity_lanes(cap.read(), cfg.sample_rate) for _ in range(40)]
    cap.close()
    lows = [p[0] for p in peaked]
    mids = [p[1] for p in peaked]
    highs = [p[2] for p in peaked]
    # Independent LFOs: at least two bands take the lead at different times.
    leaders = {int(np.argmax(p)) for p in peaked if max(p) > 1e-4}
    assert len(leaders) >= 2
    assert max(lows) > 0 and max(mids) > 0 and max(highs) > 0
