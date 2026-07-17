"""Tests for display-only event grouping (compact view)."""

from macroengine.grouping import build_groups, group_describe, group_span_delay
from macroengine.models.event import (
    KEY_DOWN,
    KEY_UP,
    MOUSE_CLICK,
    MOUSE_MOVE,
    Event,
)


def _held_key_macro():
    # A held 'a': 4 repeated key_down, then one key_up — plus a trailing click.
    evs = [Event(KEY_DOWN, 0.1, {"key": "a"}) for _ in range(4)]
    evs.append(Event(KEY_UP, 0.1, {"key": "a"}))
    evs.append(Event(MOUSE_CLICK, 0.1, {"x": 1, "y": 2, "button": "left", "pressed": True}))
    return evs


def test_detailed_is_one_group_per_event():
    evs = _held_key_macro()
    groups = build_groups(evs, compact=False)
    assert groups == [(i, 1) for i in range(len(evs))]


def test_compact_collapses_held_key():
    evs = _held_key_macro()
    groups = build_groups(evs, compact=True)
    # 4 key_downs collapse to one group; key_up and click stay separate.
    assert groups == [(0, 4), (4, 1), (5, 1)]


def test_compact_collapses_mouse_moves():
    evs = [Event(MOUSE_MOVE, 0.01, {"x": i, "y": i}) for i in range(1000)]
    evs.append(Event(MOUSE_CLICK, 0.1, {"x": 5, "y": 5, "button": "left", "pressed": True}))
    groups = build_groups(evs, compact=True)
    assert groups[0] == (0, 1000)
    assert len(groups) == 2


def test_different_keys_do_not_merge():
    evs = [Event(KEY_DOWN, 0.1, {"key": "a"}), Event(KEY_DOWN, 0.1, {"key": "b"})]
    assert build_groups(evs, compact=True) == [(0, 1), (1, 1)]


def test_group_span_delay_and_describe():
    evs = [Event(KEY_DOWN, 0.1, {"key": "a"}) for _ in range(3)]
    assert abs(group_span_delay(evs, 0, 3) - 0.3) < 1e-9
    text = group_describe(evs, 0, 3)
    assert "×3" in text and "a" in text
    # A length-1 group falls back to the event's own description.
    assert group_describe(evs, 0, 1) == evs[0].describe()
