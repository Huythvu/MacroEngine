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


def template_locate(
    image_bgr: np.ndarray, template_bgr: np.ndarray
) -> Tuple[float, Tuple[int, int, int, int]]:
    """Best match of ``template`` in ``image``: ``(score, (x, y, w, h))``.

    The box is the template's position within the searched image (top-left plus
    the template's size). If the template cannot fit, score is ``0.0``.
    """
    ih, iw = image_bgr.shape[:2]
    th, tw = template_bgr.shape[:2]
    if th > ih or tw > iw:
        return (0.0, (0, 0, tw, th))
    result = cv2.matchTemplate(image_bgr, template_bgr, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return (float(max_val), (int(max_loc[0]), int(max_loc[1]), tw, th))


def match_screen_center(
    region: Tuple[int, int, int, int], box: Tuple[int, int, int, int]
) -> Tuple[int, int]:
    """Screen coordinates of a match box's center.

    ``box`` is relative to the captured region (as returned by
    :func:`template_locate`); ``region`` is the region's screen placement.
    """
    rx, ry = region[0], region[1]
    x, y, w, h = box
    return (rx + x + w // 2, ry + y + h // 2)


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


def template_present(
    image_bgr: np.ndarray, template_png: Optional[bytes], threshold: float
) -> Tuple[bool, float]:
    """Return ``(present, best_score)`` for a stored template inside ``image``.

    ``present`` is the best match score meeting ``threshold``. The score is also
    returned so callers (e.g. the Test button) can show how strong the match is.
    """
    if not template_png:
        return (False, 0.0)
    score = template_match(image_bgr, decode_png(template_png))
    return (score >= threshold, score)


def buff_item_met(item, image_bgr: np.ndarray) -> Tuple[bool, float, bool]:
    """Evaluate one buff item against a captured group-region image.

    Returns ``(condition_met, score, present)``. Reused by the monitor loop and
    by the dialog's Test button so live behavior and the preview agree exactly.
    """
    present, score = template_present(image_bgr, item.template_png, item.match_threshold)
    if item.condition == COND_PRESENT:
        met = present
    elif item.condition == COND_ABSENT:
        met = not present
    else:
        met = False
    return (met, score, present)


def condition_met(trigger: Trigger, image_bgr: np.ndarray) -> bool:
    """Evaluate a trigger's condition against a captured region image."""
    if trigger.detection == DETECT_TEMPLATE:
        present, _ = template_present(
            image_bgr, trigger.template_png, trigger.match_threshold
        )
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
