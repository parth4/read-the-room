"""Floating card: faces, pause toggle, compact default (no fake voice bars)."""

from __future__ import annotations

import os

import pytest

try:
    import tkinter as _tkinter  # noqa: F401

    _HAS_TK = True
except ModuleNotFoundError:
    _HAS_TK = False

from madlight.faces import (
    ASSETS_DIR,
    FACE_CALM,
    FACE_FILES,
    FACE_HOT,
    FACE_PX,
    FACE_RISING,
    HEADPHONE_OFF,
    HEADPHONE_ON,
    HEADPHONES_DIR,
    face_for,
    face_png_path,
    headphone_for,
    headphone_png_path,
    load_face_image,
    load_headphone_image,
)
from madlight.heat import HeatLevel, LANE_LABELS
from madlight.ui import (
    CARD_EDGE,
    CENTER_HIT_PAD,
    DOT_PX,
    ICON_DIM,
    LANE_COUNT,
    MARK_ON_GRAY,
    MARK_ON_HEAT,
    PALETTE,
    TOGGLE_DEBOUNCE_S,
    WIN_H,
    WIN_H_BANDS,
    WIN_W,
    accept_toggle,
    center_mark_fill,
    center_ring,
    center_xy,
    led_fill,
    meter_unit,
)


def test_panel_is_compact_card_without_band_meters() -> None:
    assert 36 <= DOT_PX <= 56
    assert 180 <= WIN_W <= 260
    assert 90 <= WIN_H <= 120
    assert WIN_H < WIN_H_BANDS
    assert LANE_COUNT == 3  # optional gear path only — not the default card


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


def test_face_for_maps_listen_heat_and_drops_face_when_paused() -> None:
    assert face_for(listening=False, idle=True, level=HeatLevel.HOT) is None
    assert face_for(listening=False, idle=False, level=HeatLevel.CALM) is None
    assert face_for(listening=True, idle=True, level=HeatLevel.CALM) == FACE_CALM
    assert face_for(listening=True, idle=True, level=HeatLevel.HOT) == FACE_CALM
    assert face_for(listening=True, idle=False, level=HeatLevel.CALM) == FACE_CALM
    assert face_for(listening=True, idle=False, level=HeatLevel.RISING) == FACE_RISING
    assert face_for(listening=True, idle=False, level=HeatLevel.HOT) == FACE_HOT
    assert FACE_CALM == "🙂"
    assert FACE_RISING == "😬"
    assert FACE_HOT == "😡"
    assert "😊" not in (FACE_CALM, FACE_RISING, FACE_HOT)
    assert headphone_for(listening=True) == HEADPHONE_ON
    assert headphone_for(listening=False) == HEADPHONE_OFF
    assert HEADPHONE_ON != HEADPHONE_OFF


def test_face_asset_pngs_exist_and_load() -> None:
    notice = ASSETS_DIR.parent / "NOTICE"
    text = notice.read_text(encoding="utf-8")
    assert "Twemoji" in text
    assert "CC-BY 4.0" in text
    assert "1f642" in text
    assert "1f3a7" in text
    assert "1f60a" not in text
    assert "1f910" not in text
    assert FACE_FILES == {
        FACE_CALM: "calm.png",
        FACE_RISING: "rising.png",
        FACE_HOT: "hot.png",
    }
    assert not (ASSETS_DIR / "paused.png").exists()
    for glyph, name in FACE_FILES.items():
        path = face_png_path(glyph)
        assert path is not None and path.is_file(), name
        assert path.name == name
        img = load_face_image(glyph, FACE_PX)
        assert img is not None
        assert img.mode == "RGBA"
        assert img.size == (FACE_PX, FACE_PX)
        scaled = load_face_image(glyph, 24)
        assert scaled is not None and scaled.size == (24, 24)
    assert load_face_image("not-a-face") is None
    assert face_png_path("not-a-face") is None


def test_headphone_assets_on_and_off_are_distinct() -> None:
    notice = (HEADPHONES_DIR.parent / "NOTICE").read_text(encoding="utf-8")
    assert "headphones/on.png" in notice
    assert "headphones/off.png" in notice
    on_path = headphone_png_path(True)
    off_path = headphone_png_path(False)
    assert on_path is not None and on_path.is_file()
    assert off_path is not None and off_path.is_file()
    on_img = load_headphone_image(True)
    off_img = load_headphone_image(False)
    assert on_img is not None and off_img is not None
    assert on_img.mode == "RGBA" and off_img.mode == "RGBA"
    assert on_img.size[0] > off_img.size[0]
    worn = load_headphone_image(True, 26)
    aside = load_headphone_image(False, 26)
    assert worn is not None and aside is not None
    assert worn.tobytes() != aside.tobytes()
    assert load_headphone_image(True, 24) is not None
    assert load_headphone_image(False, 24) is not None


def test_center_ink_and_ring() -> None:
    assert center_mark_fill(listening=False, idle=True) == MARK_ON_GRAY
    assert center_mark_fill(listening=True, idle=True) == MARK_ON_GRAY
    assert center_mark_fill(listening=True, idle=False) == MARK_ON_HEAT
    assert center_ring(listening=False, idle=True, level=HeatLevel.HOT) == CARD_EDGE
    assert center_ring(listening=True, idle=True, level=HeatLevel.CALM) == ICON_DIM
    assert center_ring(listening=True, idle=False, level=HeatLevel.HOT) == PALETTE[HeatLevel.HOT]


def test_accept_toggle_debounces_double_binds() -> None:
    assert TOGGLE_DEBOUNCE_S >= 0.15
    assert accept_toggle(1.0, 1.05) is False
    assert accept_toggle(1.0, 1.0 + TOGGLE_DEBOUNCE_S + 1e-9) is True


def test_lane_ui_labels_are_not_speakers() -> None:
    assert LANE_LABELS == ("low", "mid", "high")


def test_meter_unit_clips() -> None:
    assert meter_unit(0.0, 0.1) == 0.0
    assert meter_unit(0.05, 0.1) == 0.5
    assert meter_unit(1.0, 0.1) == 1.0
    assert meter_unit(0.2, 0.0) == 0.0


def _click(win, x: int, y: int) -> None:
    """Drive the same canvas press/release path a real pointer uses."""
    rx = win.root.winfo_rootx() + x
    ry = win.root.winfo_rooty() + y
    win._canvas.event_generate("<ButtonPress-1>", x=x, y=y, rootx=rx, rooty=ry)
    win._canvas.event_generate("<ButtonRelease-1>", x=x, y=y, rootx=rx, rooty=ry)
    win.root.update()


@pytest.mark.skipif(not os.environ.get("DISPLAY") or not _HAS_TK, reason="no display/tk")
def test_dot_window_paints_faces_and_center_toggles() -> None:
    from madlight.ui import DotWindow

    hits: list[str] = []
    quits: list[str] = []
    win = DotWindow(on_off=lambda: hits.append("toggle"), on_quit=lambda: quits.append("quit"))
    try:
        win.set_state(HeatLevel.CALM, True, idle=True, wave=[0.001] * 8, lanes=(0.0, 0.0, 0.0))
        win.root.update_idletasks()
        assert win._canvas.type(win._led) == "image"
        assert win._led_fill == PALETTE["off"]
        assert win._led_ring_color == ICON_DIM
        assert win._canvas.type(win._face) == "image"
        assert "center" in win._canvas.gettags(win._face)
        assert "center" in win._canvas.gettags(win._led)
        assert win._face_glyph == FACE_CALM
        assert win._phones_mode == HEADPHONE_ON
        assert (PALETTE["off"], ICON_DIM, FACE_CALM, True) in win._center_photos
        assert win._fallback_items == []
        assert win._canvas.itemcget(win._lane_fill[0], "state") == "hidden"

        win.set_state(
            HeatLevel.HOT,
            True,
            idle=False,
            wave=[0.2] * 28,
            lanes=(0.01, 0.04, 0.08),
        )
        win.root.update_idletasks()
        assert win._led_fill == PALETTE[HeatLevel.HOT]
        assert win._led_ring_color == PALETTE[HeatLevel.HOT]
        assert win._face_glyph == FACE_HOT
        assert win._phones_mode == HEADPHONE_ON

        win.set_state(HeatLevel.RISING, True, idle=False, wave=[0.1] * 8)
        win.root.update_idletasks()
        assert win._face_glyph == FACE_RISING
        assert win._phones_mode == HEADPHONE_ON
        assert win._led_fill == PALETTE[HeatLevel.RISING]

        win.set_state(HeatLevel.HOT, False, idle=True, wave=[0.2] * 28, lanes=(0.1, 0.1, 0.1))
        win.root.update_idletasks()
        assert win._led_fill == PALETTE["off"]
        assert win._led_ring_color == CARD_EDGE
        assert win._face_glyph is None
        assert win._phones_mode == HEADPHONE_OFF

        assert win.hit_test(8, 8) == "tune"
        assert win.hit_test(46, 8) == "up"
        assert win.hit_test(64, 8) == "down"
        assert win.hit_test(80, 8) == "card"
        assert win.hit_test(WIN_W // 2, 10) == "handle"
        assert win.hit_test(WIN_W - 8, 10) == "close"
        cx, cy = center_xy()
        assert win.hit_test(cx, cy) == "center"
        assert win.hit_test(cx + DOT_PX // 2, cy) == "center"
        assert win.hit_test(cx + DOT_PX // 2 + CENTER_HIT_PAD - 1, cy) == "center"
        assert win.hit_test(28, cy) == "gear"
        assert win.hit_test(WIN_W - 28, cy) == "help"

        marks: list[str] = []
        win._on_feedback = marks.append
        win.root.update()
        _click(win, 46, 8)
        assert marks == ["up"]

        win._last_toggle = -1.0
        _click(win, cx, cy)
        assert hits == ["toggle"]
        assert win._face_glyph == FACE_CALM  # press flipped pause→listen
        assert win._phones_mode == HEADPHONE_ON

        hits.clear()
        win._last_toggle = -1.0
        _click(win, cx, cy)
        assert hits == ["toggle"]
        assert win._face_glyph is None
        assert win._phones_mode == HEADPHONE_OFF
        assert win._canvas.itemcget(win._wave_items[0], "fill") == "#3F3F3F"

        # Hold/release must not toggle a second time (debounce + click latch).
        hits.clear()
        win._last_toggle = -1.0
        rx = win.root.winfo_rootx() + cx
        ry = win.root.winfo_rooty() + cy
        win._canvas.event_generate("<ButtonPress-1>", x=cx, y=cy, rootx=rx, rooty=ry)
        win.root.update()
        assert hits == ["toggle"]
        win._canvas.event_generate("<ButtonRelease-1>", x=cx, y=cy, rootx=rx, rooty=ry)
        win.root.update()
        assert hits == ["toggle"]

        # Drag jitter after a center press still counts as one toggle.
        hits.clear()
        win._last_toggle = -1.0
        win._canvas.event_generate("<ButtonPress-1>", x=cx, y=cy, rootx=rx, rooty=ry)
        win._moved = True
        win._canvas.event_generate("<ButtonRelease-1>", x=cx + 20, y=cy + 12, rootx=rx + 20, rooty=ry + 12)
        win.root.update()
        assert hits == ["toggle"]

        # Double-delivered press (root+canvas) is still one toggle.
        hits.clear()
        win._last_toggle = -1.0
        assert win.toggle_listen() is True
        assert win.toggle_listen() is False
        assert hits == ["toggle"]

        hits.clear()
        hx, hy = WIN_W // 2, 10
        _click(win, hx, hy)
        assert hits == []

        _click(win, WIN_W - 8, 10)
        assert quits == ["quit"]
    finally:
        win.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY") or not _HAS_TK, reason="no display/tk")
def test_missing_face_png_falls_back_and_center_still_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    import madlight.ui as ui_mod

    monkeypatch.setattr(ui_mod, "load_face_image", lambda *_a, **_k: None)
    win = ui_mod.DotWindow(on_off=lambda: None, on_quit=lambda: None)
    try:
        win.set_state(HeatLevel.CALM, True, idle=True)
        win.root.update_idletasks()
        assert win._canvas.itemcget(win._face, "state") == "hidden"
        assert win._fallback_items
        assert all("center" in win._canvas.gettags(item) for item in win._fallback_items)
        cx, cy = center_xy()
        assert win.hit_test(cx, cy) == "center"
    finally:
        win.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY") or not _HAS_TK, reason="no display/tk")
def test_band_meters_are_opt_in() -> None:
    from madlight.ui import DotWindow

    shown: list[bool] = []
    win = DotWindow(
        on_off=lambda: None,
        on_quit=lambda: None,
        get_show_bands=lambda: False,
        on_show_bands=shown.append,
    )
    try:
        win.root.update_idletasks()
        assert win._canvas.itemcget(win._lane_fill[0], "state") == "hidden"
        assert win._canvas.winfo_height() == WIN_H
        win._set_show_bands(True)
        win.root.update_idletasks()
        assert shown == [True]
        assert win._canvas.itemcget(win._lane_fill[0], "state") == "normal"
        assert win._canvas.itemcget(win._band_caption, "text") == "bands · not voices"
        assert win._canvas.winfo_height() == WIN_H_BANDS
    finally:
        win.destroy()
