"""Always-on-top floating card: chrome + heat circle + meter + tray."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from typing import Any

from PIL import Image

from madlight.draw import aa_disc, aa_gear, aa_help
from madlight.faces import (
    FACE_CALM,
    FACE_HOT,
    FACE_PAUSED,
    FACE_PX,
    FACE_RISING,
    face_for,
    load_face_image,
)
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
# Disc bitmap includes the 2px ring; Pillow AA, not a Tk oval.
CIRCLE_IMG_PX = DOT_PX + 4
GEAR_PX = 22
HELP_PX = 18
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
CENTER_HIT_PAD = 8
TOGGLE_DEBOUNCE_S = 0.2

CIRCLE_X = (WIN_W - DOT_PX) // 2
CIRCLE_Y = CHROME_H + 6
ROW_CY = CIRCLE_Y + DOT_PX // 2
WAVE_Y = CIRCLE_Y + DOT_PX + 8
LANE_Y0 = WAVE_Y + WAVE_H + 16
WIN_H = WAVE_Y + WAVE_H + 12
WIN_H_BANDS = LANE_Y0 + LANE_COUNT * LANE_H + (LANE_COUNT - 1) * LANE_GAP + 14

LANE_COLORS = ("#5E9A8A", "#6B8CAE", "#8A7AA8")
WAVE_LIVE = "#B0B0B0"
WAVE_DIM = "#3F3F3F"

HELP_TEXT = (
    "Mad Light — meeting heat from the local loopback mix.\n\n"
    "Center face: click to pause / resume listening.\n"
    "  😊 calm (or silence — still listening)\n"
    "  😬 rising — energy climbing\n"
    "  😡 hot\n"
    "  🤐 paused — not listening\n\n"
    "Circle color follows heat while listening.\n"
    "Paused = dark gray + muted face.\n"
    "Silence while listening stays the calm face on gray (armed).\n\n"
    "Tuning: the Tune + / − marks mean this heat feels right / wrong\n"
    "(local log only). Gear opens Tuning — sensitivity is the\n"
    "self-improve path. Space also pauses / resumes.\n\n"
    "The strip under the face is speech energy (one waveform),\n"
    "not voices and not diarization. Optional band meters (gear)\n"
    "are frequency bands of the same mix — never a fixed “3 voices.”"
)

TUNING_HELP = (
    "Sensitivity changes when the circle goes yellow / red.\n"
    "Lower = stays green longer. Higher = yellow/red sooner.\n\n"
    "Tune + / − on the card: this heat feels right / wrong.\n"
    "Those write a local log only (no audio, no cloud).\n"
    "After several downs of the same kind, thresholds nudge."
)


def led_fill(*, listening: bool, idle: bool, level: HeatLevel) -> str:
    """Grey when paused or near-silent; heat colors only while listening with energy."""
    if (not listening) or idle:
        return PALETTE["off"]
    return PALETTE[level]


def center_mark_fill(*, listening: bool, idle: bool) -> str:
    """Ink for last-resort stick faces when a PNG asset is missing."""
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


def accept_toggle(last_mono: float, now_mono: float, window: float = TOGGLE_DEBOUNCE_S) -> bool:
    """True if a second listen/pause click should count (guards double-binds)."""
    return (now_mono - last_mono) >= window


def meter_unit(value: float, full: float) -> float:
    if full <= 0:
        return 0.0
    return max(0.0, min(1.0, float(value) / full))


def center_xy() -> tuple[int, int]:
    return WIN_W // 2, ROW_CY


def make_icon(level: HeatLevel | None, size: int = 64) -> Image.Image:
    color = PALETTE["off"] if level is None else PALETTE[level]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    disc = aa_disc(max(8, size - 12), color, outline=CARD, outline_width=2)
    x = (size - disc.width) // 2
    y = (size - disc.height) // 2
    img.alpha_composite(disc, (x, y))
    return img


def _in_rect(x: float, y: float, box: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = box
    return x0 <= x <= x1 and y0 <= y <= y1


def _in_circle(x: float, y: float, cx: int, cy: int, r: int) -> bool:
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


class DotWindow:
    """Compact always-on-top card: chrome, heat circle, one energy strip."""

    def __init__(
        self,
        *,
        on_off: Callable[[], None],
        on_quit: Callable[[], None],
        on_feedback: Callable[[str], None] | None = None,
        on_sensitivity: Callable[[str], None] | None = None,
        get_sensitivity: Callable[[], str] | None = None,
        on_show_bands: Callable[[bool], None] | None = None,
        get_show_bands: Callable[[], bool] | None = None,
    ) -> None:
        import tkinter as tk

        self._tk = tk
        self._on_off = on_off
        self._on_quit = on_quit
        self._on_feedback = on_feedback
        self._on_sensitivity = on_sensitivity
        self._get_sensitivity = get_sensitivity or (lambda: "default")
        self._on_show_bands = on_show_bands
        self._get_show_bands = get_show_bands or (lambda: False)
        self._paused = False
        self._listening = True
        self._idle = True
        self._level = HeatLevel.CALM
        self._show_bands = bool(self._get_show_bands())
        self._last_toggle = -1.0
        self._help_win: Any = None
        self._tune_win: Any = None
        self._tip: Any = None
        self._tip_job: Any = None
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
        self.root.geometry(f"{WIN_W}x{self._card_h()}+24+24")

        self._drag_x = 0
        self._drag_y = 0
        self._press_xy = (0, 0)
        self._moved = False
        self._can_drag = False
        self._center_clicked = False
        self._hit = "card"
        self._canvas = tk.Canvas(
            self.root,
            width=WIN_W,
            height=self._card_h(),
            bg=CARD,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)
        self._edge = self._canvas.create_rectangle(
            0, 0, WIN_W - 1, self._card_h() - 1, outline=CARD_EDGE, fill=CARD
        )

        hx0, hy0 = WIN_W // 2 - 14, 8
        self._handle = self._canvas.create_rectangle(
            hx0, hy0, hx0 + 28, hy0 + 3, fill=HANDLE, outline="", tags=("handle",)
        )
        self._tune_label = self._canvas.create_text(
            8, 10, text="Tune", fill=ICON, font=("Sans", 9, "bold"),
            anchor="w", tags=("tune",),
        )
        self._up_mark = self._canvas.create_text(
            46, 10, text="+", fill=ICON, font=("Sans", 13, "bold"), tags=("up",)
        )
        self._down_mark = self._canvas.create_text(
            64, 10, text="−", fill=ICON, font=("Sans", 13, "bold"), tags=("down",)
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
        self._draw_chrome_icons(cx, cy)

        self._led_photos: dict[tuple[str, str], Any] = {}
        self._led_fill = PALETTE["off"]
        self._led_ring_color = ICON_DIM
        self._led = self._canvas.create_image(cx, cy, tags=("center", "led"))
        self._face_photos: dict[str, Any] = {}
        self._face_glyph = FACE_CALM
        self._fallback_items: list[int] = []
        self._face = self._canvas.create_image(cx, cy, tags=("center", "face"))
        self._apply_circle()

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

        self._band_caption = self._canvas.create_text(
            PAD_X,
            WAVE_Y + WAVE_H + 7,
            text="bands · not voices",
            fill=ICON_DIM,
            font=("Sans", 8),
            anchor="w",
            tags=("bands",),
        )
        lane_x0, lane_x1 = PAD_X, WIN_W - PAD_X
        self._lane_track: list[int] = []
        self._lane_fill: list[int] = []
        for i in range(LANE_COUNT):
            y = LANE_Y0 + i * (LANE_H + LANE_GAP)
            self._lane_track.append(
                self._canvas.create_rectangle(
                    lane_x0, y, lane_x1, y + LANE_H, fill="#3A3A3A", outline="", tags=("bands",)
                )
            )
            self._lane_fill.append(
                self._canvas.create_rectangle(
                    lane_x0, y, lane_x0, y + LANE_H, fill=LANE_COLORS[i], outline="", tags=("bands",)
                )
            )
        self._apply_band_visibility()

        # Bind the canvas only. Root+canvas both bound → Windows overrideredirect
        # delivers press/release twice → toggle twice → pause looks broken.
        self._canvas.bind("<ButtonPress-1>", self._start_drag)
        self._canvas.bind("<B1-Motion>", self._drag)
        self._canvas.bind("<ButtonRelease-1>", self._click_or_end_drag)
        self._canvas.bind("<Button-3>", self._menu)
        self._canvas.bind("<Motion>", self._hover)
        self._canvas.bind("<Leave>", lambda _e: self._hide_tip())

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self.root.bind("<Escape>", lambda _e: self.toggle_listen())
        self.root.bind("<space>", lambda _e: self.toggle_listen())
        self._canvas.bind("<Escape>", lambda _e: self.toggle_listen())
        self._canvas.bind("<space>", lambda _e: self.toggle_listen())

    def _card_h(self) -> int:
        return WIN_H_BANDS if self._show_bands else WIN_H

    def _load_face_photo(self, glyph: str) -> Any | None:
        cached = self._face_photos.get(glyph)
        if cached is not None:
            return cached
        img = load_face_image(glyph, FACE_PX)
        if img is None:
            return None
        try:
            from PIL import ImageTk

            photo = ImageTk.PhotoImage(img, master=self.root)
        except Exception:
            return None
        self._face_photos[glyph] = photo
        return photo

    def _draw_fallback_face(self, glyph: str, color: str) -> None:
        for item in self._fallback_items:
            self._canvas.delete(item)
        self._fallback_items = []
        cx, cy = center_xy()
        eyes = ((cx - 6, cy - 4), (cx + 6, cy - 4))
        for ex, ey in eyes:
            self._fallback_items.append(
                self._canvas.create_oval(
                    ex - 1.6, ey - 1.6, ex + 1.6, ey + 1.6, fill=color, outline="", tags=("center",)
                )
            )
        if glyph == FACE_PAUSED:
            self._fallback_items.append(
                self._canvas.create_line(
                    cx - 7, cy + 6, cx + 7, cy + 6, fill=color, width=2, tags=("center",)
                )
            )
            for t in (-4, 0, 4):
                self._fallback_items.append(
                    self._canvas.create_line(
                        cx + t, cy + 3, cx + t, cy + 9, fill=color, width=1, tags=("center",)
                    )
                )
        elif glyph == FACE_HOT:
            self._fallback_items.append(
                self._canvas.create_line(cx - 8, cy - 9, cx - 3, cy - 6, fill=color, width=2, tags=("center",))
            )
            self._fallback_items.append(
                self._canvas.create_line(cx + 8, cy - 9, cx + 3, cy - 6, fill=color, width=2, tags=("center",))
            )
            self._fallback_items.append(
                self._canvas.create_arc(
                    cx - 8, cy + 2, cx + 8, cy + 12, start=20, extent=140,
                    style="arc", outline=color, width=2, tags=("center",),
                )
            )
        elif glyph == FACE_RISING:
            self._fallback_items.append(
                self._canvas.create_line(
                    cx - 7, cy + 6, cx - 3, cy + 9, cx + 3, cy + 5, cx + 7, cy + 8,
                    fill=color, width=2, smooth=True, tags=("center",),
                )
            )
        else:
            self._fallback_items.append(
                self._canvas.create_arc(
                    cx - 8, cy + 1, cx + 8, cy + 13, start=200, extent=140,
                    style="arc", outline=color, width=2, tags=("center",),
                )
            )

    def _paint_face(self, glyph: str, ink: str) -> None:
        self._face_glyph = glyph
        photo = self._load_face_photo(glyph)
        if photo is not None:
            self._canvas.itemconfig(self._face, image=photo, state="normal")
            for item in self._fallback_items:
                self._canvas.delete(item)
            self._fallback_items = []
            return
        self._canvas.itemconfig(self._face, state="hidden")
        self._draw_fallback_face(glyph, ink)

    def _draw_chrome_icons(self, cx: int, cy: int) -> None:
        from PIL import ImageTk

        self._gear_photo = ImageTk.PhotoImage(aa_gear(GEAR_PX, ICON), master=self.root)
        self._help_photo = ImageTk.PhotoImage(aa_help(HELP_PX, ICON), master=self.root)
        self._canvas.create_image(self._side_gear, cy, image=self._gear_photo, tags=("gear",))
        self._canvas.create_image(self._side_help, cy, image=self._help_photo, tags=("help",))

    def _load_disc_photo(self, fill: str, ring: str) -> Any | None:
        key = (fill, ring)
        cached = self._led_photos.get(key)
        if cached is not None:
            return cached
        img = aa_disc(CIRCLE_IMG_PX, fill, outline=ring, outline_width=2)
        try:
            from PIL import ImageTk

            photo = ImageTk.PhotoImage(img, master=self.root)
        except Exception:
            return None
        self._led_photos[key] = photo
        return photo

    def _hit_boxes(self) -> dict[str, tuple[int, int, int, int]]:
        return {
            "close": (WIN_W - 28, 0, WIN_W, CHROME_H + 2),
            "tune": (2, 0, 36, CHROME_H + 2),
            "up": (36, 0, 56, CHROME_H + 2),
            "down": (56, 0, 76, CHROME_H + 2),
            "handle": (WIN_W // 2 - 24, 0, WIN_W // 2 + 24, CHROME_H),
            "gear": (self._side_gear - 12, ROW_CY - 12, self._side_gear + 12, ROW_CY + 12),
            "help": (self._side_help - 12, ROW_CY - 12, self._side_help + 12, ROW_CY + 12),
        }

    def hit_test(self, x: float, y: float) -> str:
        boxes = self._hit_boxes()
        for name in ("close", "tune", "up", "down", "gear", "help", "handle"):
            if _in_rect(x, y, boxes[name]):
                return name
        cx, cy = center_xy()
        if _in_circle(x, y, cx, cy, DOT_PX // 2 + CENTER_HIT_PAD):
            return "center"
        return "card"

    def toggle_listen(self) -> bool:
        """Primary pause/listen control. Debounced so a double-delivered click is one toggle."""
        now = time.monotonic()
        if not accept_toggle(self._last_toggle, now):
            return False
        self._last_toggle = now
        self._listening = not self._listening
        self._paused = not self._listening
        if not self._listening:
            self._idle = True
            self._zero_wave()
        self._apply_circle()
        self._on_off()
        return True

    def _zero_wave(self) -> None:
        mid = WAVE_Y + WAVE_H / 2
        for i, item in enumerate(self._wave_items):
            x0 = self._wave_x0 + i * self._wave_bar_w
            self._canvas.coords(item, x0, mid, x0 + self._wave_bar_w - 1, mid)
            self._canvas.itemconfig(item, fill=WAVE_DIM)

    def _apply_circle(self) -> None:
        color = led_fill(listening=self._listening, idle=self._idle, level=self._level)
        ring = center_ring(listening=self._listening, idle=self._idle, level=self._level)
        ink = center_mark_fill(listening=self._listening, idle=self._idle)
        glyph = face_for(listening=self._listening, idle=self._idle, level=self._level)
        self._led_fill = color
        self._led_ring_color = ring
        photo = self._load_disc_photo(color, ring)
        if photo is not None:
            self._canvas.itemconfig(self._led, image=photo, state="normal")
        self._paint_face(glyph, ink)
        self._canvas.tag_raise("face")

    def _hover(self, event: Any) -> None:
        hit = self.hit_test(event.x, event.y)
        cursor = (
            "hand2"
            if hit in {"center", "close", "gear", "help", "up", "down", "tune"}
            else "fleur"
            if hit in {"handle", "card"}
            else "arrow"
        )
        try:
            self._canvas.configure(cursor=cursor)
        except Exception:
            pass
        tips = {
            "center": "Click to pause / listen",
            "tune": "Tuning — this heat feels right / wrong",
            "up": "Tuning: this heat feels right",
            "down": "Tuning: this heat feels wrong",
            "gear": "Tuning — sensitivity",
            "help": "What the faces and strip mean",
        }
        text = tips.get(hit)
        if text:
            self._schedule_tip(text, event.x_root, event.y_root)
        else:
            self._hide_tip()

    def _schedule_tip(self, text: str, x: int, y: int) -> None:
        if self._tip_job is not None:
            try:
                self.root.after_cancel(self._tip_job)
            except Exception:
                pass
        self._tip_job = self.root.after(380, lambda: self._show_tip(text, x, y))

    def _show_tip(self, text: str, x: int, y: int) -> None:
        self._hide_tip()
        tip = self._tk.Toplevel(self.root)
        tip.overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except self._tk.TclError:
            pass
        label = self._tk.Label(
            tip, text=text, bg="#1A1A1A", fg=ICON, font=("Sans", 9), padx=8, pady=4
        )
        label.pack()
        tip.geometry(f"+{x + 12}+{y + 16}")
        self._tip = tip

    def _hide_tip(self) -> None:
        if self._tip_job is not None:
            try:
                self.root.after_cancel(self._tip_job)
            except Exception:
                pass
            self._tip_job = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def _start_drag(self, event: Any) -> None:
        self._hide_tip()
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()
        self._press_xy = (self.root.winfo_x(), self.root.winfo_y())
        self._moved = False
        self._center_clicked = False
        self._hit = self.hit_test(event.x, event.y)
        self._can_drag = self._hit in {"handle", "card"}
        try:
            self.root.focus_set()
        except Exception:
            pass
        # Face is the primary control: toggle on press so a lost ButtonRelease
        # (common on Windows overrideredirect) cannot swallow the click.
        if self._hit == "center":
            self._center_clicked = True
            self.toggle_listen()

    def _drag(self, event: Any) -> None:
        dx = event.x_root - self.root.winfo_x() - self._drag_x
        dy = event.y_root - self.root.winfo_y() - self._drag_y
        if abs(dx) > CLICK_PX or abs(dy) > CLICK_PX:
            self._moved = True
        if self._can_drag and self._moved:
            self.root.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _click_or_end_drag(self, event: Any) -> None:
        release_hit = self.hit_test(event.x, event.y)
        # Press already toggled the face. Do not toggle again on release
        # (holding > debounce would otherwise flip twice).
        if self._center_clicked:
            self._center_clicked = False
            return
        # Release-only path: press was lost (overrideredirect) but the
        # pointer is still on the face.
        if release_hit == "center":
            self.toggle_listen()
            return
        if self._moved:
            return
        if (self.root.winfo_x(), self.root.winfo_y()) != self._press_xy and self._can_drag:
            return
        hit = self._hit
        if hit == "close":
            self._on_quit()
        elif hit in {"gear", "tune"}:
            self._show_tuning()
        elif hit == "help":
            self._show_help()
        elif hit == "up":
            self._feedback("up")
        elif hit == "down":
            self._feedback("down")

    def _feedback(self, label: str) -> None:
        if self._on_feedback is None:
            return
        mark = self._up_mark if label == "up" else self._down_mark
        flash = PALETTE[HeatLevel.CALM] if label == "up" else PALETTE[HeatLevel.HOT]
        try:
            self._canvas.itemconfig(mark, fill=flash)
            self.root.after(280, lambda: self._canvas.itemconfig(mark, fill=ICON))
        except Exception:
            pass
        self._on_feedback(label)

    def _menu(self, event: Any) -> None:
        menu = self._tk.Menu(self.root, tearoff=0, bg=CARD, fg=ICON, activebackground="#3A3A3A")
        pause_label = "Resume listening" if self._paused else "Pause listening"
        menu.add_command(label=pause_label, command=self.toggle_listen)
        menu.add_separator()
        menu.add_command(label="Tuning…", command=self._show_tuning)
        menu.add_command(label="Help — faces and meters", command=self._show_help)
        menu.add_separator()
        menu.add_command(label="Quit", command=self._on_quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_tuning(self) -> None:
        self._hide_tip()
        if self._tune_win is not None:
            try:
                self._tune_win.lift()
                return
            except Exception:
                self._tune_win = None
        win = self._tk.Toplevel(self.root)
        win.title("Tuning")
        win.configure(bg=CARD)
        try:
            win.attributes("-topmost", True)
        except self._tk.TclError:
            pass
        self._tk.Label(
            win,
            text="Tuning",
            bg=CARD,
            fg=ICON,
            font=("Sans", 12, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 2))
        self._tk.Label(
            win,
            text=TUNING_HELP,
            justify="left",
            bg=CARD,
            fg=ICON,
            font=("Sans", 10),
            wraplength=360,
        ).pack(anchor="w", padx=16, pady=(0, 10))
        self._tk.Label(
            win,
            text="Sensitivity",
            bg=CARD,
            fg=ICON,
            font=("Sans", 10, "bold"),
        ).pack(anchor="w", padx=16)
        row = self._tk.Frame(win, bg=CARD)
        row.pack(anchor="w", padx=16, pady=(4, 10))
        current = self._get_sensitivity()
        for name, title in (
            ("lower", "Lower"),
            ("default", "Default"),
            ("higher", "Higher"),
        ):
            mark = " ✓" if name == current else ""
            btn = self._tk.Button(
                row,
                text=title + mark,
                command=lambda n=name, w=win: self._pick_sensitivity(n, w),
                bg="#3A3A3A",
                fg=ICON,
                activebackground="#4A4A4A",
                relief="flat",
                padx=10,
                pady=4,
            )
            btn.pack(side="left", padx=(0, 8))
        bands = self._tk.BooleanVar(value=self._show_bands)
        self._tk.Checkbutton(
            win,
            text="Show band meters (frequency bands, not voices)",
            variable=bands,
            command=lambda: self._set_show_bands(bool(bands.get())),
            bg=CARD,
            fg=ICON,
            activebackground=CARD,
            activeforeground=ICON,
            selectcolor="#1A1A1A",
            highlightthickness=0,
        ).pack(anchor="w", padx=16, pady=(0, 14))
        win.resizable(False, False)
        self._tune_win = win
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_tuning(win))

    def _pick_sensitivity(self, name: str, win: Any) -> None:
        if self._on_sensitivity is not None:
            self._on_sensitivity(name)
        self._close_tuning(win)
        self._show_tuning()

    def _set_show_bands(self, value: bool) -> None:
        self._show_bands = value
        self._apply_band_visibility()
        if self._on_show_bands is not None:
            self._on_show_bands(value)

    def _apply_band_visibility(self) -> None:
        state = "normal" if self._show_bands else "hidden"
        for item in [self._band_caption, *self._lane_track, *self._lane_fill]:
            self._canvas.itemconfig(item, state=state)
        h = self._card_h()
        try:
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self.root.geometry(f"{WIN_W}x{h}+{x}+{y}")
        except Exception:
            self.root.geometry(f"{WIN_W}x{h}")
        self._canvas.config(height=h)
        self._canvas.coords(self._edge, 0, 0, WIN_W - 1, h - 1)

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

    def _close_tuning(self, win: Any) -> None:
        self._tune_win = None
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
        self._listening = listening
        self._paused = not listening
        self._idle = idle
        self._level = level
        self._apply_circle()

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

        if self._show_bands:
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
        self._hide_tip()
        if self._help_win is not None:
            self._close_help(self._help_win)
        if self._tune_win is not None:
            self._close_tuning(self._tune_win)
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
