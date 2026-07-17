"""Coordinate conversions between Qt logical pixels and physical screen pixels.

Qt reports positions in *logical* pixels, but ``mss`` (capture) and ``pynput``
(input injection) work in *physical* pixels. On Windows displays scaled above
100% (125%/150% are common) the two differ by the device pixel ratio, so every
Qt-selected region or point must be scaled before being stored.
"""

from __future__ import annotations

from typing import Tuple


def scale_point(x: int, y: int, ratio: float) -> Tuple[int, int]:
    """Convert a logical point to physical pixels."""
    return (round(x * ratio), round(y * ratio))


def scale_region(
    region: Tuple[int, int, int, int], ratio: float
) -> Tuple[int, int, int, int]:
    """Convert a logical (x, y, w, h) region to physical pixels.

    Width/height are scaled independently of the origin so a full-screen region
    stays full-screen (no rounding drift accumulating into the size).
    """
    x, y, w, h = region
    px, py = scale_point(x, y, ratio)
    return (px, py, max(1, round(w * ratio)), max(1, round(h * ratio)))
