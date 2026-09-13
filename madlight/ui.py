"""Always-on-top recording-pip LED, compact meter, and tray kill switch."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from typing import Any

from PIL import Image, ImageDraw

from madlight.heat import HeatLevel

# Hardware-LED / Zoom-rec pip colors (tunable via these constants).
PALETTE = {
    HeatLevel.CALM: "#3DDC97",
    HeatLevel.RISING: "#F4C15D",
    HeatLevel.HOT: "#E23D28",
    "off": "#3A3A3A",
}

RING = "#141414"

LABEL = {
    HeatLevel.CALM: "calm",
    HeatLevel.RISING: "rising",
    HeatLevel.HOT: "hot",
}

# Visible LED diameter stays pip-sized; the window is a thin strip around it.
DOT_PX = 16
PAD_PX = 4
WAVE_BARS = 28
WAVE_BAR_W = 2
WAVE_W = WAVE_BARS * WAVE_BAR_W
WAVE_H = DOT_PX
LANE_H = 3
LANE_GAP = 2
LANE_COUNT = 3
# Display scale: typical speech fills the meter; hot still clips at 1.
WAVE_FULL_RMS = 0.14
LANE_FULL_RMS = 0.055
CLICK_PX = 4

WIN_W = PAD_PX + DOT_PX + PAD_PX + WAVE_W + PAD_PX
WIN_H = PAD_PX + DOT_PX + PAD_PX + LANE_COUNT * LANE_H + (LANE_COUNT - 1) * LANE_GAP + PAD_PX

# Activity lanes: low / mid / high bands — not speaker colors.
LANE_COLORS = ("#5E9A8A", "#6B8CAE", "#8A7AA8")
WAVE_LIVE = "#9A9A9A"
WAVE_DIM = "#3F3F3F"
PAUSE_MARK = "#C8C8C8"


def led_fill(*, listening: bool, idle: bool, level: HeatLevel) -> str:
    """Grey when paused or near-silent; heat colors only while listening with energy."""
    if (not listening) or idle:
        return PALETTE["off"]
    return PALETTE[level]


def meter_unit(value: float, full: float) -> float:
    if full <= 0:
        return 0.0
    return max(0.0, min(1.0, float(value) / full))


def make_icon(level: HeatLevel | None, size: int = 64) -> Image.Image:
    color = PALETTE["off"] if level is None else PALETTE[level]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    inset = 6
    draw.ellipse((inset, inset, size - inset - 1, size - inset - 1), fill=color, outline=RING)
    return img


class DotWindow:
    """Compact always-on-top strip: LED + scrolling level + 3 activity lanes."""

    def __init__(
        self,
        *,
        on_off: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        import tkinter as tk

        self._tk = tk
        self._on_off = on_off
        self._on_quit = on_quit
        self._paused = False
        self.root = tk.Tk()
        self.root.title("Mad Light")
        # Tiny dark bezel. No chroma-key: failed transparency must not become a pink square.
        self.root.configure(bg=RING)
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self.root.overrideredirect(True)
        except tk.TclError:
            pass
        self.root.resizable(False, False)
        self.root.geometry(f"{WIN_W}x{WIN_H}+24+24")

        self._drag_x = 0
        self._drag_y = 0
        self._moved = False
        self._canvas = tk.Canvas(
            self.root,
            width=WIN_W,
            height=WIN_H,
            bg=RING,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)
        x0, y0 = PAD_PX, PAD_PX
        x1, y1 = PAD_PX + DOT_PX, PAD_PX + DOT_PX
        self._ring = self._canvas.create_oval(
            x0 - 1, y0 - 1, x1 + 1, y1 + 1, fill=RING, outline=""
        )
        self._led = self._canvas.create_oval(x0, y0, x1, y1, fill=PALETTE["off"], outline="")
        # Pause affordance: two marks on the LED (hidden while listening).
        mid_x = PAD_PX + DOT_PX / 2
        mid_y = PAD_PX + DOT_PX / 2
        self._pause_a = self._canvas.create_rectangle(
            mid_x - 3.5, mid_y - 3.5, mid_x - 1.5, mid_y + 3.5, fill=PAUSE_MARK, outline=""
        )
        self._pause_b = self._canvas.create_rectangle(
            mid_x + 1.5, mid_y - 3.5, mid_x + 3.5, mid_y + 3.5, fill=PAUSE_MARK, outline=""
        )
        self._canvas.itemconfig(self._pause_a, state="hidden")
        self._canvas.itemconfig(self._pause_b, state="hidden")

        wave_x = PAD_PX + DOT_PX + PAD_PX
        self._wave_items = [
            self._canvas.create_rectangle(
                wave_x + i * WAVE_BAR_W,
                PAD_PX + WAVE_H,
                wave_x + i * WAVE_BAR_W + WAVE_BAR_W - 1,
                PAD_PX + WAVE_H,
                fill=WAVE_LIVE,
                outline="",
            )
            for i in range(WAVE_BARS)
        ]

        lane_y0 = PAD_PX + DOT_PX + PAD_PX
        lane_x0 = PAD_PX
        lane_x1 = WIN_W - PAD_PX
        self._lane_track: list[int] = []
        self._lane_fill: list[int] = []
        for i in range(LANE_COUNT):
            y = lane_y0 + i * (LANE_H + LANE_GAP)
            self._lane_track.append(
                self._canvas.create_rectangle(
                    lane_x0, y, lane_x1, y + LANE_H, fill="#222222", outline=""
                )
            )
            self._lane_fill.append(
                self._canvas.create_rectangle(
                    lane_x0, y, lane_x0, y + LANE_H, fill=LANE_COLORS[i], outline=""
                )
            )

        for widget in (self.root, self._canvas):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._click_or_end_drag)
            widget.bind("<Button-3>", self._menu)

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self.root.bind("<Escape>", lambda _e: self._on_off())
        self.root.bind("<space>", lambda _e: self._on_off())
        self._canvas.bind("<Escape>", lambda _e: self._on_off())
        self._canvas.bind("<space>", lambda _e: self._on_off())

    def _start_drag(self, event: Any) -> None:
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()
        self._moved = False
        try:
            self.root.focus_set()
        except Exception:
            pass

    def _drag(self, event: Any) -> None:
        dx = event.x_root - self.root.winfo_x() - self._drag_x
        dy = event.y_root - self.root.winfo_y() - self._drag_y
        if abs(dx) > CLICK_PX or abs(dy) > CLICK_PX:
            self._moved = True
        if self._moved:
            self.root.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _click_or_end_drag(self, _event: Any) -> None:
        if not self._moved:
            self._on_off()

    def _menu(self, event: Any) -> None:
        menu = self._tk.Menu(self.root, tearoff=0)
        pause_label = "Resume listening" if self._paused else "Pause listening"
        menu.add_command(label=pause_label, command=self._on_off)
        menu.add_command(label="Quit", command=self._on_quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def set_state(
        self,
        level: HeatLevel,
        listening: bool,
        idle: bool = False,
        wave: Sequence[float] = (),
        lanes: Sequence[float] = (),
    ) -> None:
        self._paused = not listening
        color = led_fill(listening=listening, idle=idle, level=level)
        self._canvas.itemconfig(self._led, fill=color)
        pause_state = "normal" if not listening else "hidden"
        self._canvas.itemconfig(self._pause_a, state=pause_state)
        self._canvas.itemconfig(self._pause_b, state=pause_state)

        dim = not listening
        wave_color = WAVE_DIM if dim else WAVE_LIVE
        vals = [float(v) for v in wave][-WAVE_BARS:]
        if len(vals) < WAVE_BARS:
            vals = [0.0] * (WAVE_BARS - len(vals)) + vals
        wave_x = PAD_PX + DOT_PX + PAD_PX
        for i, item in enumerate(self._wave_items):
            unit = 0.0 if dim else meter_unit(vals[i], WAVE_FULL_RMS)
            h = max(0, int(round(unit * WAVE_H)))
            self._canvas.coords(
                item,
                wave_x + i * WAVE_BAR_W,
                PAD_PX + WAVE_H - h,
                wave_x + i * WAVE_BAR_W + WAVE_BAR_W - 1,
                PAD_PX + WAVE_H,
            )
            self._canvas.itemconfig(item, fill=wave_color)

        lane_x0 = PAD_PX
        lane_span = WIN_W - PAD_PX * 2
        lane_y0 = PAD_PX + DOT_PX + PAD_PX
        lane_vals = list(lanes) + [0.0, 0.0, 0.0]
        for i, item in enumerate(self._lane_fill):
            y = lane_y0 + i * (LANE_H + LANE_GAP)
            unit = 0.0 if dim else meter_unit(lane_vals[i], LANE_FULL_RMS)
            w = max(0, int(round(unit * lane_span)))
            self._canvas.coords(item, lane_x0, y, lane_x0 + w, y + LANE_H)
            fill = WAVE_DIM if dim else LANE_COLORS[i]
            self._canvas.itemconfig(item, fill=fill)

    def after(self, ms: int, fn: Callable[[], None]) -> None:
        self.root.after(ms, fn)

    def mainloop(self) -> None:
        self.root.mainloop()

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass


class TrayController:
    def __init__(
        self,
        *,
        on_off: Callable[[], None],
        on_quit: Callable[[], None],
        on_show_dot: Callable[[], None] | None,
        get_listening: Callable[[], bool],
        get_level: Callable[[], HeatLevel],
        get_idle: Callable[[], bool] | None = None,
    ) -> None:
        self._on_off = on_off
        self._on_quit = on_quit
        self._on_show_dot = on_show_dot
        self._get_listening = get_listening
        self._get_level = get_level
        self._get_idle = get_idle or (lambda: False)
        self._icon: Any = None

    def _display_level(self) -> HeatLevel | None:
        if not self._get_listening() or self._get_idle():
            return None
        return self._get_level()

    def start(self) -> None:
        import pystray

        menu_items = [
            pystray.MenuItem(
                "Pause — stop listening",
                lambda: self._on_off(),
                default=True,
            ),
            pystray.MenuItem(
                "Resume — start listening",
                lambda: self._on_off(),
            ),
        ]
        if self._on_show_dot is not None:
            menu_items.append(pystray.MenuItem("Show light", lambda: self._on_show_dot()))
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem("Quit", lambda: self._on_quit()))

        self._icon = pystray.Icon(
            "madlight",
            make_icon(self._display_level()),
            "Mad Light",
            pystray.Menu(*menu_items),
        )
        thread = threading.Thread(target=self._icon.run, name="madlight-tray", daemon=True)
        thread.start()

    def update(self) -> None:
        if self._icon is None:
            return
        listening = self._get_listening()
        idle = self._get_idle()
        level = self._display_level()
        try:
            self._icon.icon = make_icon(level)
            if not listening:
                title = "Mad Light — paused"
            elif idle:
                title = "Mad Light — idle"
            else:
                title = f"Mad Light — {LABEL[self._get_level()]}"
            self._icon.title = title
        except Exception:
            pass

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            pass
