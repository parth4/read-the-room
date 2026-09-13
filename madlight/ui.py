"""Always-on-top recording-pip LED and tray kill switch."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageDraw

from madlight.heat import HeatLevel

# Hardware-LED / Zoom-rec pip colors (tunable via these constants).
PALETTE = {
    HeatLevel.CALM: "#3DDC97",
    HeatLevel.RISING: "#F4C15D",
    HeatLevel.HOT: "#E23D28",
    "off": "#5A5A5A",
}

RING = "#141414"

LABEL = {
    HeatLevel.CALM: "calm",
    HeatLevel.RISING: "rising",
    HeatLevel.HOT: "hot",
}

# Visible LED diameter. Window is only slightly larger than the circle.
DOT_PX = 16
PAD_PX = 3
WIN_PX = DOT_PX + PAD_PX * 2
CHROMA = "#FF00FF"


def make_icon(level: HeatLevel | None, size: int = 64) -> Image.Image:
    color = PALETTE["off"] if level is None else PALETTE[level]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    inset = 6
    draw.ellipse((inset, inset, size - inset - 1, size - inset - 1), fill=color, outline=RING)
    return img


class DotWindow:
    """Tiny always-on-top circle — a recording-indicator LED, not a dashboard."""

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
        self.root = tk.Tk()
        self.root.title("Mad Light")
        self.root.configure(bg=CHROMA)
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self.root.overrideredirect(True)
        except tk.TclError:
            pass
        try:
            self.root.wm_attributes("-transparentcolor", CHROMA)
        except tk.TclError:
            pass
        self.root.resizable(False, False)
        self.root.geometry(f"{WIN_PX}x{WIN_PX}+24+24")

        self._drag_x = 0
        self._drag_y = 0
        self._canvas = tk.Canvas(
            self.root,
            width=WIN_PX,
            height=WIN_PX,
            bg=CHROMA,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)
        x0, y0 = PAD_PX, PAD_PX
        x1, y1 = PAD_PX + DOT_PX, PAD_PX + DOT_PX
        self._ring = self._canvas.create_oval(
            x0 - 1, y0 - 1, x1 + 1, y1 + 1, fill=RING, outline=""
        )
        self._led = self._canvas.create_oval(x0, y0, x1, y1, fill=PALETTE[HeatLevel.CALM], outline="")

        for widget in (self.root, self._canvas):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<Button-3>", self._menu)
            widget.bind("<Double-Button-1>", lambda _e: self._on_off())

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self.root.bind("<Escape>", lambda _e: self._on_off())

    def _start_drag(self, event: Any) -> None:
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag(self, event: Any) -> None:
        self.root.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _menu(self, event: Any) -> None:
        menu = self._tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Off — stop listening", command=self._on_off)
        menu.add_command(label="Quit", command=self._on_quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def set_state(self, level: HeatLevel, listening: bool) -> None:
        color = PALETTE["off"] if not listening else PALETTE[level]
        self._canvas.itemconfig(self._led, fill=color)

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
    ) -> None:
        self._on_off = on_off
        self._on_quit = on_quit
        self._on_show_dot = on_show_dot
        self._get_listening = get_listening
        self._get_level = get_level
        self._icon: Any = None

    def start(self) -> None:
        import pystray

        listening = self._get_listening()
        level = self._get_level() if listening else None
        menu_items = [
            pystray.MenuItem(
                "Off — stop listening",
                lambda: self._on_off(),
                default=True,
            ),
            pystray.MenuItem(
                "On — start listening",
                lambda: self._on_off(),
            ),
        ]
        if self._on_show_dot is not None:
            menu_items.append(pystray.MenuItem("Show light", lambda: self._on_show_dot()))
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem("Quit", lambda: self._on_quit()))

        self._icon = pystray.Icon(
            "madlight",
            make_icon(level),
            "Mad Light",
            pystray.Menu(*menu_items),
        )
        thread = threading.Thread(target=self._icon.run, name="madlight-tray", daemon=True)
        thread.start()

    def update(self) -> None:
        if self._icon is None:
            return
        listening = self._get_listening()
        level = self._get_level() if listening else None
        try:
            self._icon.icon = make_icon(level)
            self._icon.title = (
                "Mad Light — off" if not listening else f"Mad Light — {LABEL[self._get_level()]}"
            )
        except Exception:
            pass

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            pass
