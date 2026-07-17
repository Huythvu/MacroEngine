"""Fast screen-region capture via mss, returned as an OpenCV BGR image."""

from __future__ import annotations

from typing import Tuple

import numpy as np


def grab_region(region: Tuple[int, int, int, int]) -> np.ndarray:
    """Capture ``(x, y, width, height)`` and return an HxWx3 BGR uint8 array.

    A fresh ``mss`` instance is created per call because a single instance is not
    safe to share across threads.
    """
    import mss  # imported lazily so headless/test environments need not have a display

    x, y, w, h = region
    with mss.mss() as sct:
        shot = sct.grab({"left": int(x), "top": int(y), "width": int(w), "height": int(h)})
    # mss returns BGRA; drop alpha and keep BGR for OpenCV.
    arr = np.asarray(shot, dtype=np.uint8)  # HxWx4 (BGRA)
    return arr[:, :, :3].copy()
