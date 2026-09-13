"""Anti-aliased chrome for the heat circle (Pillow, not Tk ovals)."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Draw 4× then LANCZOS-downscale so Windows does not show Tk's pixel stairs.
AA_SCALE = 4

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.removeprefix("#")
    if len(h) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha


def _ui_font(size_px: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size_px)
    return ImageFont.load_default()


def aa_disc(
    diameter: int,
    fill: str,
    *,
    outline: str | None = None,
    outline_width: int = 2,
    scale: int = AA_SCALE,
) -> Image.Image:
    """Smooth filled circle. Supersample + downscale; do not use Tk `create_oval`."""
    if diameter < 1 or scale < 1:
        raise ValueError("diameter and scale must be >= 1")
    hi = diameter * scale
    img = Image.new("RGBA", (hi, hi), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # One dest-pixel inset so the AA fringe is not clipped by the bitmap edge.
    pad = scale
    box = (pad, pad, hi - pad - 1, hi - pad - 1)
    fill_c = rgba(fill)
    if outline:
        width = max(scale, outline_width * scale)
        draw.ellipse(box, fill=fill_c, outline=rgba(outline), width=width)
    else:
        draw.ellipse(box, fill=fill_c)
    return img.resize((diameter, diameter), Image.Resampling.LANCZOS)


def aa_gear(size: int, color: str, scale: int = AA_SCALE) -> Image.Image:
    """Outline cog at `size` px, same silhouette as the old Tk polygon."""
    if size < 1 or scale < 1:
        raise ValueError("size and scale must be >= 1")
    hi = size * scale
    img = Image.new("RGBA", (hi, hi), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = hi / 2
    # Previous Tk gear used r=7.2 / 4.6 in a ~20px side hit target.
    outer = 0.36 * hi
    inner = 0.23 * hi
    pts: list[float] = []
    for i in range(16):
        ang = math.radians(i * 22.5 - 11.25)
        r = outer if i % 2 == 0 else inner
        pts.extend((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    stroke = max(scale, int(round(1.15 * scale)))
    draw.polygon(pts, outline=rgba(color), width=stroke)
    hole = 0.11 * hi
    draw.ellipse(
        (cx - hole, cy - hole, cx + hole, cy + hole),
        outline=rgba(color),
        width=stroke,
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def aa_help(size: int, color: str, scale: int = AA_SCALE) -> Image.Image:
    """Circle + question mark, supersampled."""
    if size < 1 or scale < 1:
        raise ValueError("size and scale must be >= 1")
    hi = size * scale
    img = Image.new("RGBA", (hi, hi), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = scale
    ink = rgba(color)
    draw.ellipse((pad, pad, hi - pad - 1, hi - pad - 1), outline=ink, width=max(scale, scale))
    font = _ui_font(max(8, int(size * 0.56 * scale)))
    bbox = draw.textbbox((0, 0), "?", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (hi - tw) / 2 - bbox[0]
    y = (hi - th) / 2 - bbox[1] - 0.35 * scale
    draw.text((x, y), "?", font=font, fill=ink)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def paste_at(base: Image.Image, overlay: Image.Image, xy: tuple[int, int]) -> Image.Image:
    """Alpha-composite `overlay` at `xy` (copy)."""
    out = base.copy()
    out.alpha_composite(overlay, xy)
    return out


def paste_centered(base: Image.Image, overlay: Image.Image) -> Image.Image:
    """Alpha-composite `overlay` in the middle of `base` (copy)."""
    x = (base.width - overlay.width) // 2
    y = (base.height - overlay.height) // 2
    return paste_at(base, overlay, (x, y))


def compose_center(
    disc: Image.Image,
    *,
    face: Image.Image | None,
    headphones: Image.Image | None,
    listening: bool,
) -> Image.Image:
    """AA disc + worn headphones behind the face, or set-aside cans when paused."""
    out = disc.copy()
    if listening and headphones is not None:
        x = (out.width - headphones.width) // 2
        out.alpha_composite(headphones, (x, 1))
    if face is not None:
        out = paste_centered(out, face)
    elif headphones is not None and not listening:
        out = paste_centered(out, headphones)
    return out


def edge_alpha_values(img: Image.Image) -> list[int]:
    """Unique alpha samples — used to prove the disc is not a hard 0/255 stair."""
    raw = img.tobytes()
    return sorted({raw[i] for i in range(3, len(raw), 4)})
