"""Round-trip and behavior tests for the serializable data models."""

from macroengine.models.event import KEY_DOWN, MOUSE_CLICK, Event
from macroengine.models.macro import Macro
from macroengine.models.trigger import (
    COND_RATIO_ABOVE,
    DETECT_COLOR,
    Trigger,
    load_triggers,
    save_triggers,
)


def test_event_roundtrip():
    ev = Event(type=KEY_DOWN, delay=0.25, data={"key": "a"})
    assert Event.from_dict(ev.to_dict()) == ev


def test_event_negative_delay_clamped():
    assert Event(type=KEY_DOWN, delay=-5, data={"key": "a"}).delay == 0.0


def test_macro_roundtrip(tmp_path):
    macro = Macro(
        name="test",
        loop_count=3,
        events=[
            Event(type=KEY_DOWN, delay=0.0, data={"key": "h"}),
            Event(type=MOUSE_CLICK, delay=0.1, data={"x": 10, "y": 20, "button": "left", "pressed": True}),
        ],
    )
    path = tmp_path / "m.json"
    macro.save(path)
    loaded = Macro.load(path)
    assert loaded.name == "test"
    assert loaded.loop_count == 3
    assert [e.to_dict() for e in loaded.events] == [e.to_dict() for e in macro.events]


def test_macro_duration():
    macro = Macro(events=[Event(KEY_DOWN, 0.2, {"key": "a"}), Event(KEY_DOWN, 0.3, {"key": "b"})])
    assert abs(macro.duration() - 0.5) < 1e-9


def test_trigger_roundtrip(tmp_path):
    trig = Trigger(
        name="hp",
        region=(5, 6, 100, 20),
        detection=DETECT_COLOR,
        condition=COND_RATIO_ABOVE,
        ratio_threshold=0.4,
        template_png=b"\x89PNGfake",
        cooldown_s=2.5,
    )
    path = tmp_path / "t.json"
    save_triggers([trig], path)
    loaded = load_triggers(path)
    assert len(loaded) == 1
    got = loaded[0]
    assert got.name == "hp"
    assert got.region == (5, 6, 100, 20)
    assert got.detection == DETECT_COLOR
    assert got.condition == COND_RATIO_ABOVE
    assert abs(got.ratio_threshold - 0.4) < 1e-9
    assert got.template_png == b"\x89PNGfake"
    assert abs(got.cooldown_s - 2.5) < 1e-9
