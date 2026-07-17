"""Headless tests for the vision primitives and per-trigger evaluation.

Synthetic images are generated with numpy so no display or screen grab is needed.
"""

import numpy as np

from macroengine.models.trigger import (
    COND_ABSENT,
    COND_PRESENT,
    COND_RATIO_ABOVE,
    COND_RATIO_BELOW,
    DETECT_COLOR,
    DETECT_TEMPLATE,
    Trigger,
)
from macroengine.vision import detector


def _solid(h, w, bgr):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = bgr
    return img


def _textured(h, w, seed):
    # Deterministic noise: a realistic (non-uniform) stand-in for an icon.
    # TM_CCOEFF_NORMED is only meaningful for templates that have variance.
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def test_template_match_finds_patch():
    template = _textured(10, 10, seed=1)
    scene = _solid(50, 50, (0, 0, 0))
    scene[10:20, 10:20] = template  # embed the exact patch
    assert detector.template_match(scene, template) > 0.95


def test_template_match_absent_is_low():
    template = _textured(10, 10, seed=1)
    scene = _textured(50, 50, seed=2)  # unrelated texture, patch not present
    assert detector.template_match(scene, template) < 0.6


def test_template_larger_than_scene_returns_zero():
    scene = _solid(5, 5, (0, 0, 0))
    template = _solid(10, 10, (0, 0, 0))
    assert detector.template_match(scene, template) == 0.0


def test_png_roundtrip():
    img = _solid(8, 8, (10, 20, 30))
    decoded = detector.decode_png(detector.encode_png(img))
    assert np.array_equal(img, decoded)


def test_color_ratio_full_and_none():
    red = _solid(20, 20, (0, 0, 255))
    lower, upper = (0, 100, 100), (10, 255, 255)
    assert detector.color_ratio(red, lower, upper) > 0.99
    black = _solid(20, 20, (0, 0, 0))
    assert detector.color_ratio(black, lower, upper) < 0.01


def test_condition_template_present_absent():
    patch = _textured(10, 10, seed=7)
    scene = _solid(40, 40, (0, 0, 0))
    scene[5:15, 5:15] = patch
    template_png = detector.encode_png(patch)
    present = Trigger(detection=DETECT_TEMPLATE, condition=COND_PRESENT,
                      template_png=template_png, match_threshold=0.8)
    absent = Trigger(detection=DETECT_TEMPLATE, condition=COND_ABSENT,
                     template_png=template_png, match_threshold=0.8)
    assert detector.condition_met(present, scene) is True
    assert detector.condition_met(absent, scene) is False

    empty = _textured(40, 40, seed=99)  # patch not present
    assert detector.condition_met(present, empty) is False
    assert detector.condition_met(absent, empty) is True


def test_condition_color_thresholds():
    red = _solid(20, 20, (0, 0, 255))
    above = Trigger(detection=DETECT_COLOR, condition=COND_RATIO_ABOVE,
                    ratio_threshold=0.5, hsv_lower=(0, 100, 100), hsv_upper=(10, 255, 255))
    below = Trigger(detection=DETECT_COLOR, condition=COND_RATIO_BELOW,
                    ratio_threshold=0.5, hsv_lower=(0, 100, 100), hsv_upper=(10, 255, 255))
    assert detector.condition_met(above, red) is True
    assert detector.condition_met(below, red) is False
