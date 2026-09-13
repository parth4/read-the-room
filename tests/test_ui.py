"""Floating card stays compact; idle/pause paint grey, not calm-green."""

from __future__ import annotations

import os

import pytest

from madlight.heat import HeatLevel, LANE_LABELS
from madlight.ui import (
    CARD_EDGE,
    ICON_DIM,
    DOT_PX,
    LANE_COUNT,
    MARK_ON_GRAY,
    MARK_ON_HEAT,
    PALETTE,
    WIN_H,
    WIN_W,
    center_mark,
    center_mark_fill,
    center_ring,
    center_xy,
    led_fill,
    meter_unit,
)


def test_panel_is_compact_card() -> None:
    assert 36 <= DOT_PX <= 56
    assert 180 <= WIN_W <= 260
    assert 90 <= WIN_H <= 150
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


def test_center_mark_splits_pause_from_listen() -> None:
    assert center_mark(listening=False) == "pause"
    assert center_mark(listening=True) == "mic"
    assert center_mark_fill(listening=False, idle=True) == MARK_ON_GRAY
    assert center_mark_fill(listening=True, idle=True) == MARK_ON_GRAY
    assert center_mark_fill(listening=True, idle=False) == MARK_ON_HEAT
    assert center_ring(listening=False, idle=True, level=HeatLevel.HOT) == CARD_EDGE
    assert center_ring(listening=True, idle=True, level=HeatLevel.CALM) == ICON_DIM
    assert center_ring(listening=True, idle=False, level=HeatLevel.HOT) == PALETTE[HeatLevel.HOT]


def test_lane_ui_labels_are_not_speakers() -> None:
    assert LANE_LABELS == ("low", "mid", "high")


def test_meter_unit_clips() -> None:
    assert meter_unit(0.0, 0.1) == 0.0
    assert meter_unit(0.05, 0.1) == 0.5
    assert meter_unit(1.0, 0.1) == 1.0
    assert meter_unit(0.2, 0.0) == 0.0


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="no display")
def test_dot_window_paints_and_chrome_hits() -> None:
    from madlight.ui import DotWindow

    hits: list[str] = []
    quits: list[str] = []
    win = DotWindow(on_off=lambda: hits.append("toggle"), on_quit=lambda: quits.append("quit"))
    try:
        win.set_state(HeatLevel.CALM, True, idle=True, wave=[0.001] * 8, lanes=(0.0, 0.0, 0.0))
        win.root.update_idletasks()
        assert win._canvas.itemcget(win._led, "fill") == PALETTE["off"]
        assert win._canvas.itemcget(win._led_ring, "outline") == ICON_DIM
        assert win._canvas.itemcget(win._pause_a, "state") == "hidden"
        assert win._canvas.itemcget(win._mic_head, "state") == "normal"
        win.set_state(
            HeatLevel.HOT,
            True,
            idle=False,
            wave=[0.2] * 28,
            lanes=(0.01, 0.04, 0.08),
        )
        win.root.update_idletasks()
        assert win._canvas.itemcget(win._led, "fill") == PALETTE[HeatLevel.HOT]
        assert win._canvas.itemcget(win._mic_head, "state") == "normal"
        assert win._canvas.itemcget(win._pause_a, "state") == "hidden"
        win.set_state(HeatLevel.HOT, False, idle=True, wave=[0.2] * 28, lanes=(0.1, 0.1, 0.1))
        win.root.update_idletasks()
        assert win._canvas.itemcget(win._led, "fill") == PALETTE["off"]
        assert win._canvas.itemcget(win._led_ring, "outline") == CARD_EDGE
        assert win._canvas.itemcget(win._pause_a, "state") == "normal"
        assert win._canvas.itemcget(win._mic_head, "state") == "hidden"

        assert win.hit_test(8, 8) == "up"
        assert win.hit_test(28, 8) == "down"
        assert win.hit_test(50, 8) == "card"
        assert win.hit_test(WIN_W // 2, 10) == "handle"
        assert win.hit_test(WIN_W - 8, 10) == "close"
        cx, cy = center_xy()
        assert win.hit_test(cx, cy) == "center"
        assert win.hit_test(28, cy) == "gear"
        assert win.hit_test(WIN_W - 28, cy) == "help"

        marks: list[str] = []
        win._on_feedback = marks.append
        win.root.update()
        win.root.event_generate(
            "<ButtonPress-1>",
            x=8,
            y=8,
            rootx=win.root.winfo_rootx() + 8,
            rooty=win.root.winfo_rooty() + 8,
        )
        win.root.event_generate(
            "<ButtonRelease-1>",
            x=8,
            y=8,
            rootx=win.root.winfo_rootx() + 8,
            rooty=win.root.winfo_rooty() + 8,
        )
        win.root.update()
        assert marks == ["up"]

        win.root.update()
        rx = win.root.winfo_rootx() + cx
        ry = win.root.winfo_rooty() + cy
        win.root.event_generate("<ButtonPress-1>", x=cx, y=cy, rootx=rx, rooty=ry)
        win.root.event_generate("<ButtonRelease-1>", x=cx, y=cy, rootx=rx, rooty=ry)
        win.root.update()
        assert hits == ["toggle"]

        hits.clear()
        hx, hy = WIN_W // 2, 10
        win.root.event_generate(
            "<ButtonPress-1>", x=hx, y=hy, rootx=win.root.winfo_rootx() + hx, rooty=win.root.winfo_rooty() + hy
        )
        win.root.event_generate(
            "<ButtonRelease-1>", x=hx, y=hy, rootx=win.root.winfo_rootx() + hx, rooty=win.root.winfo_rooty() + hy
        )
        win.root.update()
        assert hits == []

        win.root.event_generate(
            "<ButtonPress-1>",
            x=WIN_W - 8,
            y=10,
            rootx=win.root.winfo_rootx() + WIN_W - 8,
            rooty=win.root.winfo_rooty() + 10,
        )
        win.root.event_generate(
            "<ButtonRelease-1>",
            x=WIN_W - 8,
            y=10,
            rootx=win.root.winfo_rootx() + WIN_W - 8,
            rooty=win.root.winfo_rooty() + 10,
        )
        win.root.update()
        assert quits == ["quit"]
    finally:
        win.destroy()
