"""Always-on-top color pill and tray kill switch."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageDraw

from madlite.heat import HeatLevel

PALETTE = {
    HeatLevel.CALM: "#3DDC97",
    HeatLevel.RISING: "#F4C15D",
    HeatLevel.HOT: "#F07167",
    "off": "#6B6B6B",
}

INK = {
    HeatLevel.CALM: "#102018",
    HeatLevel.RISING: "#2A1C00",
    HeatLevel.HOT: "#2A0A08",
    "off": "#F2F2F2",
}

LABEL = {
    HeatLevel.CALM: "CALM",
    HeatLevel.RISING: "RISING",
    HeatLevel.HOT: "HOT",
}


def make_icon(level: HeatLevel | None, size: int = 64) -> Image.Image:
    color = PALETTE["off"] if level is None else PALETTE[level]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    inset = 4
    draw.ellipse((inset, inset, size - inset - 1, size - inset - 1), fill=color)
    return img


class PillWindow:
    """Tiny always-on-top heat pill with an obvious Off control."""

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
        self.root.title("Mad Lite")
        self.root.configure(bg=PALETTE[HeatLevel.CALM])
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self.root.overrideredirect(True)
        except tk.TclError:
            pass
        self.root.resizable(False, False)
        self.root.geometry("220x48+24+24")

        self._drag_x = 0
        self._drag_y = 0
        self._frame = tk.Frame(self.root, bg=PALETTE[HeatLevel.CALM], padx=10, pady=8)
        self._frame.pack(fill="both", expand=True)

        self._label = tk.Label(
            self._frame,
            text="CALM",
            fg=INK[HeatLevel.CALM],
            bg=PALETTE[HeatLevel.CALM],
            font=("sans-serif", 12, "bold"),
            width=8,
            anchor="w",
        )
        self._label.pack(side="left")

        self._off = tk.Button(
            self._frame,
            text="OFF",
            command=self._on_off,
            bg="#1B1B1B",
            fg="#F2F2F2",
            activebackground="#111111",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=10,
            pady=2,
            font=("sans-serif", 10, "bold"),
            cursor="hand2",
            highlightthickness=0,
            bd=0,
        )
        self._off.pack(side="right")

        for widget in (self.root, self._frame, self._label):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<Button-3>", self._menu)

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
        if not listening:
            color = PALETTE["off"]
            ink = INK["off"]
            text = "OFF"
            btn = "ON"
        else:
            color = PALETTE[level]
            ink = INK[level]
            text = LABEL[level]
            btn = "OFF"
        self.root.configure(bg=color)
        self._frame.configure(bg=color)
        self._label.configure(text=text, bg=color, fg=ink)
        self._off.configure(text=btn, command=self._on_off)

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
        on_show_pill: Callable[[], None] | None,
        get_listening: Callable[[], bool],
        get_level: Callable[[], HeatLevel],
    ) -> None:
        self._on_off = on_off
        self._on_quit = on_quit
        self._on_show_pill = on_show_pill
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
        if self._on_show_pill is not None:
            menu_items.append(pystray.MenuItem("Show pill", lambda: self._on_show_pill()))
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem("Quit", lambda: self._on_quit()))

        self._icon = pystray.Icon(
            "madlite",
            make_icon(level),
            "Mad Lite",
            pystray.Menu(*menu_items),
        )
        thread = threading.Thread(target=self._icon.run, name="madlite-tray", daemon=True)
        thread.start()

    def update(self) -> None:
        if self._icon is None:
            return
        listening = self._get_listening()
        level = self._get_level() if listening else None
        try:
            self._icon.icon = make_icon(level)
            self._icon.title = (
                "Mad Lite — off" if not listening else f"Mad Lite — {LABEL[self._get_level()]}"
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
