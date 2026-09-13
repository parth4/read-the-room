"""LED must stay a recording-pip, not a dashboard."""

from madlight.ui import DOT_PX, WIN_PX, PALETTE
from madlight.heat import HeatLevel


def test_dot_is_pip_sized() -> None:
    assert DOT_PX <= 20
    assert WIN_PX <= 28
    assert WIN_PX > DOT_PX


def test_palette_has_three_heats_and_off() -> None:
    assert PALETTE[HeatLevel.CALM].startswith("#")
    assert PALETTE[HeatLevel.RISING].startswith("#")
    assert PALETTE[HeatLevel.HOT].startswith("#")
    assert PALETTE["off"].startswith("#")
    assert len({PALETTE[HeatLevel.CALM], PALETTE[HeatLevel.RISING], PALETTE[HeatLevel.HOT]}) == 3
