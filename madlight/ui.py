"""Always-on-top floating card: chrome + heat circle + meter + tray."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable, Sequence
from typing import Any

from PIL import Image, ImageDraw

from madlight.heat import HeatLevel

# Heat / idle fills. Card chrome is a separate dark-gray panel.
PALETTE = {
    HeatLevel.CALM: "#3DDC97",
    HeatLevel.RISING: "#F4C15D",
    HeatLevel.HOT: "#E23D28",
    "off": "#3A3A3A",
}

CARD = "#2C2C2C"
CARD_EDGE = "#3A3A3A"
RING = CARD
ICON = "#C8C8C8"
ICON_DIM = "#8A8A8A"
HANDLE = "#9A9A9A"
MARK_ON_GRAY = "#E4E4E4"
MARK_ON_HEAT = "#1A1A1A"

LABEL = {
    HeatLevel.CALM: "calm",
    HeatLevel.RISING: "rising",
    HeatLevel.HOT: "hot",
}

# Compact Voice Access–style card. Center circle is the listening/heat control.
DOT_PX = 44
CHROME_H = 20
PAD_X = 16
WIN_W = 232
WAVE_BARS = 28
WAVE_H = 12
LANE_H = 4
LANE_GAP = 3
LANE_COUNT = 3
WAVE_FULL_RMS = 0.14
LANE_FULL_RMS = 0.04
CLICK_PX = 8

CIRCLE_X = (WIN_W - DOT_PX) // 2
CIRCLE_Y = CHROME_H + 6
ROW_CY = CIRCLE_Y + DOT_PX // 2
WAVE_Y = CIRCLE_Y + DOT_PX + 8
LANE_Y0 = WAVE_Y + WAVE_H + 6
WIN_H = LANE_Y0 + LANE_COUNT * LANE_H + (LANE_COUNT - 1) * LANE_GAP + 10

LANE_COLORS = ("#5E9A8A", "#6B8CAE", "#8A7AA8")
WAVE_LIVE = "#B0B0B0"
WAVE_DIM = "#3F3F3F"

HELP_TEXT = (
    "Mad Light — meeting heat from the local loopback mix.\n\n"
    "Center: click to pause / resume listening.\n"
    "Mic = listening (armed). Pause bars = capture off.\n"
    "Green calm · amber rising · red hot.\n"
    "Dark gray + mic = silence, still listening.\n"
    "Dark gray + pause = paused, not listening.\n\n"
    "Activity lanes are low / mid / high frequency bands "
    "of the same mix — not speaker names, not diarization."
)


def led_fill(*, listening: bool, idle: bool, level: HeatLevel) -> str:
    """Grey when paused or near-silent; heat colors only while listening with energy."""
    if (not listening) or idle:
        return PALETTE["off"]
    return PALETTE[level]


def center_mark(*, listening: bool) -> str:
    """Glyph on the heat circle: pause bars when capture is off, mic when armed."""
    return "mic" if listening else "pause"


def center_mark_fill(*, listening: bool, idle: bool) -> str:
    """Light marks on grey; dark marks so heat color stays the hero."""
    if (not listening) or idle:
        return MARK_ON_GRAY
    return MARK_ON_HEAT


def center_ring(*, listening: bool, idle: bool, level: HeatLevel) -> str:
    """Paused stays a dead edge; idle listening reads armed; heat matches the fill."""
    if not listening:
        return CARD_EDGE
    if idle:
        return ICON_DIM
    return PALETTE[level]


def meter_unit(value: float, full: float) -> float:
    if full <= 0:
        return 0.0
    return max(0.0, min(1.0, float(value) / full))


def center_xy() -> tuple[int, int]:
    return WIN_W // 2, ROW_CY


def make_icon(level: HeatLevel | None, size: int = 64) -> Image.Image:
    color = PALETTE["off"] if level is None else PALETTE[level]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    inset = 6
    draw.ellipse((inset, inset, size - inset - 1, size - inset - 1), fill=color, outline=CARD)
    return img


def _in_rect(x: float, y: float, box: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = box
    return x0 <= x <= x1 and y0 <= y <= y1


def _in_circle(x: float, y: float, cx: int, cy: int, r: int) -> bool:
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


class DotWindow:
    """Compact always-on-top card: chrome, heat circle, level, activity lanes."""

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
        self._help_win: Any = None
        self.root = tk.Tk()
        self.root.title("Mad Light")
        self.root.configure(bg=CARD)
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
        self._press_xy = (0, 0)
        self._moved = False
        self._can_drag = False
        self._hit = "card"
        self._canvas = tk.Canvas(
            self.root,
            width=WIN_W,
            height=WIN_H,
            bg=CARD,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)
        self._canvas.create_rectangle(0, 0, WIN_W - 1, WIN_H - 1, outline=CARD_EDGE, fill=CARD)

        hx0, hy0 = WIN_W // 2 - 14, 8
        self._handle = self._canvas.create_rectangle(
            hx0, hy0, hx0 + 28, hy0 + 3, fill=HANDLE, outline="", tags=("handle",)
        )
        self._close_x = WIN_W - 16
        self._close_y = 10
        self._close_a = self._canvas.create_line(
            self._close_x - 4, self._close_y - 4, self._close_x + 4, self._close_y + 4,
            fill=ICON, width=2, tags=("close",),
        )
        self._close_b = self._canvas.create_line(
            self._close_x - 4, self._close_y + 4, self._close_x + 4, self._close_y - 4,
            fill=ICON, width=2, tags=("close",),
        )

        cx, cy = center_xy()
        self._side_gear = 28
        self._side_help = WIN_W - 28
        self._draw_gear(self._side_gear, cy)
        self._help_ring = self._canvas.create_oval(
            self._side_help - 8, cy - 8, self._side_help + 8, cy + 8,
            outline=ICON, width=1, tags=("help",),
        )
        self._help_mark = self._canvas.create_text(
            self._side_help, cy, text="?", fill=ICON, font=("Sans", 10, "bold"), tags=("help",)
        )

        r = DOT_PX / 2
        self._led_ring = self._canvas.create_oval(
            cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2, outline=ICON_DIM, width=2
        )
        self._led = self._canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r, fill=PALETTE["off"], outline=""
        )
        self._pause_a = self._canvas.create_rectangle(
            cx - 7, cy - 9, cx - 2, cy + 9, fill=MARK_ON_GRAY, outline=""
        )
        self._pause_b = self._canvas.create_rectangle(
            cx + 2, cy - 9, cx + 7, cy + 9, fill=MARK_ON_GRAY, outline=""
        )
        self._draw_mic(cx, cy)
        # Default: listening + idle (armed) until the first tick.
        self._canvas.itemconfig(self._pause_a, state="hidden")
        self._canvas.itemconfig(self._pause_b, state="hidden")

        wave_x = PAD_X
        wave_span = WIN_W - PAD_X * 2
        self._wave_bar_w = max(2, wave_span // WAVE_BARS)
        self._wave_x0 = wave_x + (wave_span - self._wave_bar_w * WAVE_BARS) // 2
        mid = WAVE_Y + WAVE_H / 2
        self._wave_items = [
            self._canvas.create_rectangle(
                self._wave_x0 + i * self._wave_bar_w,
                mid,
                self._wave_x0 + i * self._wave_bar_w + self._wave_bar_w - 1,
                mid,
                fill=WAVE_LIVE,
                outline="",
            )
            for i in range(WAVE_BARS)
        ]

        lane_x0, lane_x1 = PAD_X, WIN_W - PAD_X
        self._lane_track: list[int] = []
        self._lane_fill: list[int] = []
        for i in range(LANE_COUNT):
            y = LANE_Y0 + i * (LANE_H + LANE_GAP)
            self._lane_track.append(
                self._canvas.create_rectangle(
                    lane_x0, y, lane_x1, y + LANE_H, fill="#3A3A3A", outline=""
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
            widget.bind("<Motion>", self._hover)

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self.root.bind("<Escape>", lambda _e: self._on_off())
        self.root.bind("<space>", lambda _e: self._on_off())
        self._canvas.bind("<Escape>", lambda _e: self._on_off())
        self._canvas.bind("<space>", lambda _e: self._on_off())

    def _draw_mic(self, cx: int, cy: int) -> None:
        # Classic capsule + U-yoke + stem — reads as a listen control at 44px.
        self._mic_head = self._canvas.create_oval(
            cx - 4, cy - 12, cx + 4, cy, fill=MARK_ON_GRAY, outline="", tags=("mic",)
        )
        self._mic_yoke = self._canvas.create_arc(
            cx - 8, cy - 5, cx + 8, cy + 9,
            start=180,
            extent=180,
            style="arc",
            outline=MARK_ON_GRAY,
            width=2,
            tags=("mic",),
        )
        self._mic_stem = self._canvas.create_line(
            cx, cy + 8, cx, cy + 12, fill=MARK_ON_GRAY, width=2, tags=("mic",)
        )
        self._mic_base = self._canvas.create_line(
            cx - 5, cy + 12, cx + 5, cy + 12, fill=MARK_ON_GRAY, width=2, tags=("mic",)
        )

    def _paint_mic(self, color: str, state: str) -> None:
        self._canvas.itemconfig(self._mic_head, fill=color, state=state)
        self._canvas.itemconfig(self._mic_yoke, outline=color, state=state)
        self._canvas.itemconfig(self._mic_stem, fill=color, state=state)
        self._canvas.itemconfig(self._mic_base, fill=color, state=state)

    def _draw_gear(self, cx: int, cy: int) -> None:
        # Outline cog — chrome only, not a settings panel.
        teeth: list[float] = []
        for i in range(16):
            ang = math.radians(i * 22.5 - 11.25)
            r = 7.2 if i % 2 == 0 else 4.6
            teeth.extend((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        self._canvas.create_polygon(*teeth, outline=ICON, fill="", width=1, tags=("gear",))
        self._canvas.create_oval(
            cx - 2.2, cy - 2.2, cx + 2.2, cy + 2.2, outline=ICON, width=1, tags=("gear",)
        )

    def _hit_boxes(self) -> dict[str, tuple[int, int, int, int]]:
        return {
            "close": (WIN_W - 28, 0, WIN_W, CHROME_H + 2),
            "handle": (WIN_W // 2 - 24, 0, WIN_W // 2 + 24, CHROME_H),
            "gear": (self._side_gear - 12, ROW_CY - 12, self._side_gear + 12, ROW_CY + 12),
            "help": (self._side_help - 12, ROW_CY - 12, self._side_help + 12, ROW_CY + 12),
        }

    def hit_test(self, x: float, y: float) -> str:
        boxes = self._hit_boxes()
        for name in ("close", "gear", "help", "handle"):
            if _in_rect(x, y, boxes[name]):
                return name
        cx, cy = center_xy()
        if _in_circle(x, y, cx, cy, DOT_PX // 2 + 2):
            return "center"
        return "card"

    def _hover(self, event: Any) -> None:
        hit = self.hit_test(event.x, event.y)
        cursor = "hand2" if hit in {"center", "close", "gear", "help"} else "fleur" if hit in {"handle", "card"} else "arrow"
        try:
            self._canvas.configure(cursor=cursor)
        except Exception:
            pass

    def _start_drag(self, event: Any) -> None:
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()
        self._press_xy = (self.root.winfo_x(), self.root.winfo_y())
        self._moved = False
        self._hit = self.hit_test(event.x, event.y)
        self._can_drag = self._hit in {"handle", "card"}
        try:
            self.root.focus_set()
        except Exception:
            pass

    def _drag(self, event: Any) -> None:
        dx = event.x_root - self.root.winfo_x() - self._drag_x
        dy = event.y_root - self.root.winfo_y() - self._drag_y
        if abs(dx) > CLICK_PX or abs(dy) > CLICK_PX:
            self._moved = True
        if self._can_drag and self._moved:
            self.root.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _click_or_end_drag(self, event: Any) -> None:
        if self._moved:
            return
        if (self.root.winfo_x(), self.root.winfo_y()) != self._press_xy and self._can_drag:
            return
        hit = self._hit
        if hit == "center":
            self._on_off()
        elif hit == "close":
            self._on_quit()
        elif hit == "gear":
            self._menu(event)
        elif hit == "help":
            self._show_help()

    def _menu(self, event: Any) -> None:
        menu = self._tk.Menu(self.root, tearoff=0, bg=CARD, fg=ICON, activebackground="#3A3A3A")
        pause_label = "Resume listening" if self._paused else "Pause listening"
        menu.add_command(label=pause_label, command=self._on_off)
        menu.add_separator()
        menu.add_command(label="Activity lanes: low / mid / high (not speakers)", command=self._show_help)
        menu.add_separator()
        menu.add_command(label="Quit", command=self._on_quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_help(self) -> None:
        if self._help_win is not None:
            try:
                self._help_win.lift()
                return
            except Exception:
                self._help_win = None
        win = self._tk.Toplevel(self.root)
        win.title("Mad Light")
        win.configure(bg=CARD)
        try:
            win.attributes("-topmost", True)
        except self._tk.TclError:
            pass
        msg = self._tk.Label(
            win,
            text=HELP_TEXT,
            justify="left",
            bg=CARD,
            fg=ICON,
            font=("Sans", 10),
            padx=16,
            pady=14,
        )
        msg.pack()
        win.resizable(False, False)
        self._help_win = win
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_help(win))

    def _close_help(self, win: Any) -> None:
        self._help_win = None
        try:
            win.destroy()
        except Exception:
            pass

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
        ink = center_mark_fill(listening=listening, idle=idle)
        mark = center_mark(listening=listening)
        self._canvas.itemconfig(self._led, fill=color)
        self._canvas.itemconfig(self._led_ring, outline=center_ring(listening=listening, idle=idle, level=level))
        pause_state = "normal" if mark == "pause" else "hidden"
        mic_state = "normal" if mark == "mic" else "hidden"
        self._canvas.itemconfig(self._pause_a, state=pause_state, fill=ink)
        self._canvas.itemconfig(self._pause_b, state=pause_state, fill=ink)
        self._paint_mic(ink, mic_state)

        dim = not listening
        wave_color = WAVE_DIM if dim else WAVE_LIVE
        vals = [float(v) for v in wave][-WAVE_BARS:]
        if len(vals) < WAVE_BARS:
            vals = [0.0] * (WAVE_BARS - len(vals)) + vals
        mid = WAVE_Y + WAVE_H / 2
        half = WAVE_H / 2
        for i, item in enumerate(self._wave_items):
            unit = 0.0 if dim else meter_unit(vals[i], WAVE_FULL_RMS)
            h = max(0.0, unit * half)
            x0 = self._wave_x0 + i * self._wave_bar_w
            self._canvas.coords(item, x0, mid - h, x0 + self._wave_bar_w - 1, mid + h)
            self._canvas.itemconfig(item, fill=wave_color)

        lane_x0 = PAD_X
        lane_span = WIN_W - PAD_X * 2
        lane_vals = list(lanes) + [0.0, 0.0, 0.0]
        for i, item in enumerate(self._lane_fill):
            y = LANE_Y0 + i * (LANE_H + LANE_GAP)
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
        if self._help_win is not None:
            self._close_help(self._help_win)
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
