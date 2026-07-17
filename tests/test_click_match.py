"""Tests for click-on-match: template location + screen-coordinate math."""

import numpy as np

from macroengine.models.routine import STEP_WAIT_VISION, RoutineStep
from macroengine.models.trigger import ACTION_CLICK_MATCH, Trigger
from macroengine.vision import detector


def _textured(h, w, seed):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def test_template_locate_finds_position():
    patch = _textured(10, 12, seed=11)  # h=10, w=12
    scene = np.zeros((60, 80, 3), dtype=np.uint8)
    scene[20:30, 40:52] = patch  # top-left at (x=40, y=20)
    score, (x, y, w, h) = detector.template_locate(scene, patch)
    assert score > 0.95
    assert (x, y) == (40, 20)
    assert (w, h) == (12, 10)


def test_template_locate_too_large_scores_zero():
    scene = _textured(5, 5, seed=1)
    tpl = _textured(10, 10, seed=2)
    score, box = detector.template_locate(scene, tpl)
    assert score == 0.0


def test_match_screen_center():
    # Region at screen (100, 200); match box at (40, 20) size 12x10
    # -> center = (100+40+6, 200+20+5)
    assert detector.match_screen_center((100, 200, 300, 100), (40, 20, 12, 10)) == (146, 225)


def test_locate_agrees_with_match_score():
    """template_locate's score must match template_match (same metric)."""
    patch = _textured(8, 8, seed=3)
    scene = np.zeros((40, 40, 3), dtype=np.uint8)
    scene[10:18, 22:30] = patch
    score_locate, _ = detector.template_locate(scene, patch)
    score_match = detector.template_match(scene, patch)
    assert abs(score_locate - score_match) < 1e-6


def test_trigger_click_match_action_roundtrip():
    trig = Trigger(name="accept", action=ACTION_CLICK_MATCH)
    restored = Trigger.from_dict(trig.to_dict())
    assert restored.action == ACTION_CLICK_MATCH
    assert "click the found image" in restored.describe()


def test_routine_step_click_on_match_roundtrip():
    step = RoutineStep(type=STEP_WAIT_VISION, click_on_match=True)
    restored = RoutineStep.from_dict(step.to_dict())
    assert restored.click_on_match is True
    assert "then click it" in restored.describe()
    # Default stays off for old files.
    old = RoutineStep.from_dict({"type": STEP_WAIT_VISION})
    assert old.click_on_match is False
