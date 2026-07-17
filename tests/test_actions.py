"""Tests for the unified action vocabulary and its round-trip on models."""

from macroengine.models import actions
from macroengine.models.buff import BuffItem
from macroengine.models.trigger import Trigger


def test_action_constants_stable_strings():
    # Values must equal the historical per-model constants for file compatibility.
    assert actions.PRESS_KEY == "press_key"
    assert actions.TYPE_TEXT == "type_text"
    assert actions.CLICK_AT == "click"
    assert actions.CLICK_MATCH == "click_match"
    assert actions.RUN_MACRO == "run_macro"


def test_describe_action():
    assert "press 'a'" == actions.describe_action(actions.PRESS_KEY, key="a")
    assert "type '123asd'" == actions.describe_action(actions.TYPE_TEXT, text="123asd")
    assert "left-click (5, 6)" == actions.describe_action(actions.CLICK_AT, x=5, y=6)
    assert "click the found image" == actions.describe_action(actions.CLICK_MATCH)


def test_trigger_new_action_fields_roundtrip():
    t = Trigger(
        name="clicky",
        action=actions.CLICK_AT,
        action_x=840, action_y=512, action_button="right",
        action_text="hi",
    )
    r = Trigger.from_dict(t.to_dict())
    assert r.action == actions.CLICK_AT
    assert (r.action_x, r.action_y, r.action_button) == (840, 512, "right")
    assert r.action_text == "hi"
    assert "right-click (840, 512)" in r.describe()


def test_buffitem_new_action_fields_roundtrip():
    b = BuffItem(name="cleanse", action=actions.TYPE_TEXT, action_text="/cleanse")
    r = BuffItem.from_dict(b.to_dict())
    assert r.action == actions.TYPE_TEXT
    assert r.action_text == "/cleanse"
    assert "type '/cleanse'" in r.describe()


def test_old_files_default_new_action_fields():
    # A trigger dict without the new keys still loads (fields default).
    old = Trigger(name="old").to_dict()
    for k in ("action_text", "action_x", "action_y", "action_button"):
        old.pop(k, None)
    r = Trigger.from_dict(old)
    assert r.action_text == "" and r.action_x == 0 and r.action_button == "left"
