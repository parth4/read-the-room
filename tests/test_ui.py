"""LED stays compact; idle/pause paint grey, not calm-green."""

from __future__ import annotations

import os

import pytest

from madlight.heat import HeatLevel, LANE_LABELS
from madlight.ui import DOT_PX, LANE_COUNT, PALETTE, WIN_H, WIN_W, led_fill, meter_unit


def test_dot_stays_pip_sized_inside_a_compact_strip() -> None:
    assert DOT_PX <= 20
    assert WIN_W <= 100
    assert WIN_H <= 56
    assert WIN_W > DOT_PX
    assert WIN_H >= DOT_PX
    assert LANE_COUNT == 3


def test_palette_has_three_heats_and_off() -> None:
    assert PALETTE[HeatLevel.CALM].startswith("#")
    assert PALETTE[HeatLevel.RISING].startswith("#")
    assert PALETTE[HeatLevel.HOT].startswith("#")
    assert PALETTE["off"].startswith("#")
    assert len({PALETTE[HeatLevel.CALM], PALETTE[HeatLevel.RISING], PALETTE[HeatLevel.HOT]}) == 3


def test_led_fill_idle_and_paused_are_gray() -> None:
    gray = PALETTE["off"]
    assert led_fill(listening=False, idle=False, level=HeatLevel.CALM) == gray
    assert led_fill(listening=True, idle=True, level=HeatLevel.CALM) == gray
    assert led_fill(listening=True, idle=True, level=HeatLevel.HOT) == gray
    assert led_fill(listening=True, idle=False, level=HeatLevel.CALM) == PALETTE[HeatLevel.CALM]
    assert led_fill(listening=True, idle=False, level=HeatLevel.RISING) == PALETTE[HeatLevel.RISING]
    assert led_fill(listening=True, idle=False, level=HeatLevel.HOT) == PALETTE[HeatLevel.HOT]


def test_lane_ui_labels_are_not_speakers() -> None:
    assert LANE_LABELS == ("low", "mid", "high")


def test_meter_unit_clips() -> None:
    assert meter_unit(0.0, 0.1) == 0.0
    assert meter_unit(0.05, 0.1) == 0.5
    assert meter_unit(1.0, 0.1) == 1.0
    assert meter_unit(0.2, 0.0) == 0.0


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="no display")
def test_dot_window_paints_idle_hot_and_paused() -> None:
    from madlight.ui import DotWindow

    hits: list[str] = []
    win = DotWindow(on_off=lambda: hits.append("toggle"), on_quit=lambda: None)
    try:
        win.set_state(HeatLevel.CALM, True, idle=True, wave=[0.001] * 8, lanes=(0.0, 0.0, 0.0))
        win.root.update_idletasks()
        assert win._canvas.itemcget(win._led, "fill") == PALETTE["off"]
        win.set_state(
            HeatLevel.HOT,
            True,
            idle=False,
            wave=[0.2] * 28,
            lanes=(0.01, 0.04, 0.08),
        )
        win.root.update_idletasks()
        assert win._canvas.itemcget(win._led, "fill") == PALETTE[HeatLevel.HOT]
        win.set_state(HeatLevel.HOT, False, idle=True, wave=[0.2] * 28, lanes=(0.1, 0.1, 0.1))
        win.root.update_idletasks()
        assert win._canvas.itemcget(win._led, "fill") == PALETTE["off"]
        assert win._canvas.itemcget(win._pause_a, "state") == "normal"
        win.root.update()
        rx = win.root.winfo_rootx() + 8
        ry = win.root.winfo_rooty() + 8
        win.root.event_generate("<ButtonPress-1>", x=8, y=8, rootx=rx, rooty=ry)
        win.root.event_generate("<ButtonRelease-1>", x=8, y=8, rootx=rx, rooty=ry)
        win.root.update()
        assert hits == ["toggle"]
    finally:
        win.destroy()
