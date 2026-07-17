"""Tests for the routine model: round-trip, describe, and the Trigger bridge."""

import numpy as np

from macroengine.models.routine import (
    STEP_MACRO,
    STEP_WAIT,
    STEP_WAIT_VISION,
    TIMEOUT_CONTINUE,
    TIMEOUT_STOP,
    Routine,
    RoutineStep,
)
from macroengine.models.trigger import COND_PRESENT, DETECT_TEMPLATE
from macroengine.vision import detector


def _textured(h, w, seed):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def _sample_routine():
    return Routine(
        name="daily",
        loop_count=2,
        steps=[
            RoutineStep(type=STEP_MACRO, name="walk", macro_path="walk.json", loop_override=3),
            RoutineStep(type=STEP_WAIT, wait_s=2.5, jitter_s=0.5),
            RoutineStep(
                type=STEP_WAIT_VISION,
                name="loot icon",
                region=(5, 6, 100, 50),
                detection=DETECT_TEMPLATE,
                template_png=b"\x89PNGfake",
                condition=COND_PRESENT,
                timeout_s=15.0,
                on_timeout=TIMEOUT_CONTINUE,
            ),
        ],
    )


def test_routine_roundtrip(tmp_path):
    routine = _sample_routine()
    path = tmp_path / "r.json"
    routine.save(path)
    loaded = Routine.load(path)
    assert loaded.name == "daily"
    assert loaded.loop_count == 2
    assert [s.type for s in loaded.steps] == [STEP_MACRO, STEP_WAIT, STEP_WAIT_VISION]
    m, w, v = loaded.steps
    assert (m.macro_path, m.loop_override) == ("walk.json", 3)
    assert (w.wait_s, w.jitter_s) == (2.5, 0.5)
    assert v.region == (5, 6, 100, 50)
    assert v.template_png == b"\x89PNGfake"
    assert v.condition == COND_PRESENT
    assert (v.timeout_s, v.on_timeout) == (15.0, TIMEOUT_CONTINUE)


def test_step_describe():
    m, w, v = _sample_routine().steps
    assert "walk.json" in m.describe() and "×3" in m.describe()
    assert "2.5" in w.describe()
    assert "loot icon" in v.describe() and "continue" in v.describe()
    stop_step = RoutineStep(type=STEP_WAIT_VISION, timeout_s=0, on_timeout=TIMEOUT_STOP)
    assert "forever" in stop_step.describe()


def test_to_trigger_parity_with_detector():
    """A vision step evaluated via to_trigger() must behave exactly like the
    equivalent standalone trigger (runner-vs-dialog parity)."""
    patch = _textured(10, 10, seed=4)
    scene = np.zeros((40, 40, 3), dtype=np.uint8)
    scene[5:15, 5:15] = patch
    step = RoutineStep(
        type=STEP_WAIT_VISION,
        detection=DETECT_TEMPLATE,
        template_png=detector.encode_png(patch),
        condition=COND_PRESENT,
        match_threshold=0.8,
    )
    assert detector.condition_met(step.to_trigger(), scene) is True
    empty = _textured(40, 40, seed=77)
    assert detector.condition_met(step.to_trigger(), empty) is False


def test_disabled_steps_survive_roundtrip(tmp_path):
    routine = _sample_routine()
    routine.steps[1].enabled = False
    path = tmp_path / "r.json"
    routine.save(path)
    assert [s.enabled for s in Routine.load(path).steps] == [True, False, True]
