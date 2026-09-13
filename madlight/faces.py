"""Bundled Twemoji PNG faces and headphone badges for the heat circle."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from madlight.heat import HeatLevel

FACE_CALM = "🙂"
FACE_RISING = "😬"
FACE_HOT = "😡"

# Fits inside the worn-headphone overlay on the 44px circle.
FACE_PX = 26

FACE_FILES: dict[str, str] = {
    FACE_CALM: "calm.png",
    FACE_RISING: "rising.png",
    FACE_HOT: "hot.png",
}

HEADPHONE_ON = "🎧"
HEADPHONE_OFF = "🎧-off"
HEADPHONE_ON_PX = 36
HEADPHONE_OFF_PX = 26

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "faces"
HEADPHONES_DIR = Path(__file__).resolve().parent / "assets" / "headphones"


def face_for(*, listening: bool, idle: bool, level: HeatLevel) -> str | None:
    """Heat face while listening. Pause drops the face — headphones carry on/off."""
    if not listening:
        return None
    if idle or level is HeatLevel.CALM:
        return FACE_CALM
    if level is HeatLevel.RISING:
        return FACE_RISING
    return FACE_HOT


def headphone_for(*, listening: bool) -> str:
    """🎧 worn on the circle while listening; dimmed / set-aside when paused."""
    return HEADPHONE_ON if listening else HEADPHONE_OFF


def face_png_path(glyph: str) -> Path | None:
    name = FACE_FILES.get(glyph)
    if name is None:
        return None
    path = ASSETS_DIR / name
    return path if path.is_file() else None


def headphone_png_path(listening: bool) -> Path | None:
    path = HEADPHONES_DIR / ("on.png" if listening else "off.png")
    return path if path.is_file() else None


def _scale_rgba(path: Path, size: int) -> Image.Image | None:
    try:
        with Image.open(path) as src:
            img = src.convert("RGBA")
    except OSError:
        return None
    if size > 0 and img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def load_face_image(glyph: str, size: int = FACE_PX) -> Image.Image | None:
    """RGBA Pillow image scaled to ``size``, or None if the asset is missing."""
    path = face_png_path(glyph)
    if path is None:
        return None
    return _scale_rgba(path, size)


def load_headphone_image(listening: bool, size: int | None = None) -> Image.Image | None:
    """Worn (color) or set-aside (dimmed) headphone PNG, or None if missing."""
    path = headphone_png_path(listening)
    if path is None:
        return None
    if size is None:
        size = HEADPHONE_ON_PX if listening else HEADPHONE_OFF_PX
    return _scale_rgba(path, size)
