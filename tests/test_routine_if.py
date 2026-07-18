"""Tests for inline-recorded macro steps and the If-vision decision step."""

from macroengine.models import actions
from macroengine.models.actions import Action
from macroengine.models.macro import Macro
from macroengine.models.event import KEY_DOWN, Event
from macroengine.models.routine import (
    STEP_IF_VISION,
    STEP_MACRO,
    Routine,
    RoutineStep,
)


def test_inline_macro_roundtrip(tmp_path):
    macro = Macro(name="inline", events=[Event(KEY_DOWN, 0.1, {"key": "a"})])
    step = RoutineStep(type=STEP_MACRO, inline_macro=macro.to_dict(), loop_override=2)
    routine = Routine(name="r", steps=[step])
    path = tmp_path / "r.json"
    routine.save(path)
    loaded = Routine.load(path).steps[0]
    assert loaded.inline_macro is not None
    assert loaded.inline_macro["events"][0]["data"]["key"] == "a"
    assert "recorded (1 events)" in loaded.describe()
    # Inline macro rebuilds into a real Macro.
    assert Macro.from_dict(loaded.inline_macro).events[0].data["key"] == "a"


def test_if_vision_roundtrip(tmp_path):
    step = RoutineStep(
        type=STEP_IF_VISION,
        name="loot",
        then_action=Action(kind=actions.PRESS_KEY, key="f"),
        else_action=Action(kind=actions.NONE),
    )
    routine = Routine(name="r", steps=[step])
    path = tmp_path / "r.json"
    routine.save(path)
    loaded = Routine.load(path).steps[0]
    assert loaded.type == STEP_IF_VISION
    assert loaded.then_action.kind == actions.PRESS_KEY
    assert loaded.then_action.key == "f"
    assert loaded.else_action.kind == actions.NONE
    d = loaded.describe()
    assert "If loot" in d and "press 'f'" in d and "do nothing" in d


def test_action_roundtrip_and_describe():
    a = Action(kind=actions.CLICK_AT, x=10, y=20, button="right")
    assert Action.from_dict(a.to_dict()) == a
    assert "right-click (10, 20)" in a.describe()
    assert Action().describe() == "do nothing"


def test_defaults_for_old_files():
    # A step dict without the new keys still loads with sane defaults.
    step = RoutineStep.from_dict({"type": STEP_MACRO, "macro_path": "x.json"})
    assert step.inline_macro is None
    assert step.then_action.kind == actions.NONE
    assert step.else_action.kind == actions.NONE
