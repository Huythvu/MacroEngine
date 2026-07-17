"""Pure image-analysis primitives plus per-trigger condition evaluation.

Everything here operates on OpenCV BGR arrays and has no GUI/screen dependency,
so it can be unit-tested headlessly against saved sample images.
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from ..models.trigger import (
    COND_ABSENT,
    COND_PRESENT,
    COND_RATIO_ABOVE,
    COND_RATIO_BELOW,
    DETECT_COLOR,
    DETECT_TEMPLATE,
    Trigger,
)


def encode_png(image_bgr: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image_bgr)
    if not ok:
        raise ValueError("Failed to PNG-encode image")
    return buf.tobytes()


def decode_png(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode PNG bytes")
    return img


def template_match(image_bgr: np.ndarray, template_bgr: np.ndarray) -> float:
    """Return the best normalized match score (0..1) of ``template`` in ``image``.

    If the template is larger than the search image the match is impossible and
    ``0.0`` is returned.
    """
    ih, iw = image_bgr.shape[:2]
    th, tw = template_bgr.shape[:2]
    if th > ih or tw > iw:
        return 0.0
    result = cv2.matchTemplate(image_bgr, template_bgr, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return float(max_val)


def color_ratio(
    image_bgr: np.ndarray,
    hsv_lower: Tuple[int, int, int],
    hsv_upper: Tuple[int, int, int],
) -> float:
    """Fraction (0..1) of pixels whose HSV value falls within the band."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower, dtype=np.uint8), np.array(hsv_upper, dtype=np.uint8))
    total = mask.size
    if total == 0:
        return 0.0
    return float(np.count_nonzero(mask)) / float(total)


def condition_met(trigger: Trigger, image_bgr: np.ndarray) -> bool:
    """Evaluate a trigger's condition against a captured region image."""
    if trigger.detection == DETECT_TEMPLATE:
        if not trigger.template_png:
            return False
        score = template_match(image_bgr, decode_png(trigger.template_png))
        present = score >= trigger.match_threshold
        if trigger.condition == COND_PRESENT:
            return present
        if trigger.condition == COND_ABSENT:
            return not present
        return False

    if trigger.detection == DETECT_COLOR:
        ratio = color_ratio(image_bgr, trigger.hsv_lower, trigger.hsv_upper)
        if trigger.condition == COND_RATIO_ABOVE:
            return ratio > trigger.ratio_threshold
        if trigger.condition == COND_RATIO_BELOW:
            return ratio < trigger.ratio_threshold
        return False

    return False
