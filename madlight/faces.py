"""Bundled Twemoji PNG faces for the heat circle."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from madlight.heat import HeatLevel

FACE_CALM = "🙂"
FACE_RISING = "😐"
FACE_HOT = "😠"
FACE_PAUSED = "🤐"

# Fits inside the 44px circle with a ring of fill color still visible.
FACE_PX = 30

FACE_FILES: dict[str, str] = {
    FACE_CALM: "calm.png",
    FACE_RISING: "rising.png",
    FACE_HOT: "hot.png",
    FACE_PAUSED: "paused.png",
}

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "faces"


def face_for(*, listening: bool, idle: bool, level: HeatLevel) -> str:
    """Which bundled face to show. Silence while listening stays calm, not muted."""
    if not listening:
        return FACE_PAUSED
    if idle or level is HeatLevel.CALM:
        return FACE_CALM
    if level is HeatLevel.RISING:
        return FACE_RISING
    return FACE_HOT


def face_png_path(glyph: str) -> Path | None:
    name = FACE_FILES.get(glyph)
    if name is None:
        return None
    path = ASSETS_DIR / name
    return path if path.is_file() else None


def load_face_image(glyph: str, size: int = FACE_PX) -> Image.Image | None:
    """RGBA Pillow image scaled to ``size``, or None if the asset is missing."""
    path = face_png_path(glyph)
    if path is None:
        return None
    try:
        with Image.open(path) as src:
            img = src.convert("RGBA")
    except OSError:
        return None
    if size > 0 and img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img
