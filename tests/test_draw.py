"""Anti-aliased disc / chrome — no Tk ovals, soft edges after 4× downscale."""

from __future__ import annotations

from madlight.draw import (
    AA_SCALE,
    aa_disc,
    aa_gear,
    aa_help,
    edge_alpha_values,
    paste_centered,
    rgba,
)
from madlight.faces import FACE_CALM, FACE_PX, load_face_image
from madlight.ui import CIRCLE_IMG_PX, DOT_PX, PALETTE
from madlight.heat import HeatLevel


def test_aa_disc_has_soft_fringe_not_binary_stairs() -> None:
    img = aa_disc(CIRCLE_IMG_PX, PALETTE[HeatLevel.CALM], outline=PALETTE[HeatLevel.CALM])
    assert img.size == (CIRCLE_IMG_PX, CIRCLE_IMG_PX)
    assert img.mode == "RGBA"
    alphas = edge_alpha_values(img)
    mid = [a for a in alphas if 0 < a < 255]
    assert len(mid) >= 8, alphas
    # Interior is the mint fill, fully opaque.
    cx = cy = CIRCLE_IMG_PX // 2
    pix = img.getpixel((cx, cy))
    assert pix[3] == 255
    assert pix[1] > 180
    # Corners stay empty so the card shows through.
    for xy in ((0, 0), (0, CIRCLE_IMG_PX - 1), (CIRCLE_IMG_PX - 1, 0)):
        assert img.getpixel(xy)[3] == 0


def test_naive_ellipse_is_harder_than_aa_disc() -> None:
    from PIL import Image, ImageDraw

    naive = Image.new("RGBA", (CIRCLE_IMG_PX, CIRCLE_IMG_PX), (0, 0, 0, 0))
    ImageDraw.Draw(naive).ellipse((2, 2, CIRCLE_IMG_PX - 3, CIRCLE_IMG_PX - 3), fill=(61, 220, 151, 255))
    aa = aa_disc(CIRCLE_IMG_PX, "#3DDC97")
    naive_mid = [a for a in edge_alpha_values(naive) if 0 < a < 255]
    aa_mid = [a for a in edge_alpha_values(aa) if 0 < a < 255]
    assert len(aa_mid) > len(naive_mid)


def test_aa_scale_is_supersampled() -> None:
    assert AA_SCALE >= 2
    assert CIRCLE_IMG_PX == DOT_PX + 4


def test_chrome_icons_are_rgba_with_aa() -> None:
    gear = aa_gear(22, "#C8C8C8")
    help_icon = aa_help(18, "#C8C8C8")
    assert gear.size == (22, 22) and gear.mode == "RGBA"
    assert help_icon.size == (18, 18) and help_icon.mode == "RGBA"
    assert any(0 < a < 255 for a in edge_alpha_values(gear))
    assert any(0 < a < 255 for a in edge_alpha_values(help_icon))


def test_face_composites_crisp_on_aa_disc() -> None:
    disc = aa_disc(CIRCLE_IMG_PX, PALETTE[HeatLevel.CALM], outline=PALETTE[HeatLevel.CALM])
    face = load_face_image(FACE_CALM, FACE_PX)
    assert face is not None
    badge = paste_centered(disc, face)
    assert badge.size == disc.size
    # Face pixels landed in the middle (not a blank disc).
    mid = badge.getpixel((CIRCLE_IMG_PX // 2, CIRCLE_IMG_PX // 2))
    disc_mid = disc.getpixel((CIRCLE_IMG_PX // 2, CIRCLE_IMG_PX // 2))
    assert mid != disc_mid
    assert mid[3] == 255


def test_rgba_parses_hex() -> None:
    assert rgba("#3DDC97") == (61, 220, 151, 255)
    assert rgba("E23D28", 128) == (226, 61, 40, 128)
