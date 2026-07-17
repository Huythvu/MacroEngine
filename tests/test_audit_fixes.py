"""Tests for the audit fixes: edge-click trimming and DPI coordinate scaling."""

from macroengine.models.event import KEY_DOWN, KEY_UP, MOUSE_CLICK, MOUSE_MOVE, Event
from macroengine.models.macro import trim_edge_clicks
from macroengine.screenmath import scale_point, scale_region


def _click(pressed, x=10, y=10):
    return Event(MOUSE_CLICK, 0.05, {"x": x, "y": y, "button": "left", "pressed": pressed})


def _key(name, down=True):
    return Event(KEY_DOWN if down else KEY_UP, 0.05, {"key": name})


# -- trim_edge_clicks ---------------------------------------------------------

def test_trim_removes_leading_and_trailing_pairs():
    evs = [_click(True), _click(False), _key("a"), _key("a", down=False),
           _click(True), _click(False)]
    out = trim_edge_clicks(evs)
    assert [e.type for e in out] == [KEY_DOWN, KEY_UP]


def test_trim_lone_half_pairs():
    # Lone leading release (start-click press predates the listeners) and a lone
    # trailing press (stop-click release arrives after listeners stop).
    evs = [_click(False), _key("x"), _click(True)]
    out = trim_edge_clicks(evs)
    assert len(out) == 1 and out[0].type == KEY_DOWN


def test_trim_respects_edge_flags():
    evs = [_click(True), _click(False), _key("a"), _click(True), _click(False)]
    only_lead = trim_edge_clicks(evs, leading=True, trailing=False)
    assert [e.type for e in only_lead] == [KEY_DOWN, MOUSE_CLICK, MOUSE_CLICK]
    only_trail = trim_edge_clicks(evs, leading=False, trailing=True)
    assert [e.type for e in only_trail] == [MOUSE_CLICK, MOUSE_CLICK, KEY_DOWN]


def test_trim_never_touches_keys_or_moves():
    evs = [_key("a"), Event(MOUSE_MOVE, 0.01, {"x": 1, "y": 2}), _key("a", down=False)]
    assert trim_edge_clicks(evs) == evs


def test_trim_click_only_macro_loses_at_most_one_pair_per_edge():
    evs = [_click(True), _click(False)] * 3  # 3 genuine click pairs
    out = trim_edge_clicks(evs)
    assert len(out) == 2  # middle pair survives


# -- DPI scaling --------------------------------------------------------------

def test_scale_identity_at_100_percent():
    assert scale_point(640, 480, 1.0) == (640, 480)
    assert scale_region((10, 20, 300, 200), 1.0) == (10, 20, 300, 200)


def test_scale_at_150_percent():
    assert scale_point(100, 200, 1.5) == (150, 300)
    assert scale_region((100, 200, 40, 30), 1.5) == (150, 300, 60, 45)


def test_scale_rounds_and_keeps_min_size():
    x, y, w, h = scale_region((3, 3, 1, 1), 1.25)
    assert (x, y) == (4, 4)  # 3.75 rounds to 4
    assert w >= 1 and h >= 1