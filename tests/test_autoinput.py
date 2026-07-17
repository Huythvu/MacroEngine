"""Tests for auto inputs: model round-trip, scheduling math, and persistence."""

from macroengine.models.autoinput import (
    AUTO_CLICK,
    AUTO_PRESS_KEY,
    AutoInput,
)
from macroengine.models.store import load_watchers, save_watchers


def test_autoinput_roundtrip():
    a = AutoInput(
        name="spam 2",
        action=AUTO_PRESS_KEY,
        key="2",
        interval_s=0.25,
        jitter_s=0.05,
    )
    restored = AutoInput.from_dict(a.to_dict())
    assert restored == a


def test_autoinput_click_roundtrip():
    a = AutoInput(action=AUTO_CLICK, x=840, y=512, button="right", interval_s=0.1)
    restored = AutoInput.from_dict(a.to_dict())
    assert restored.action == AUTO_CLICK
    assert (restored.x, restored.y, restored.button) == (840, 512, "right")


def test_next_interval_exact_and_jittered():
    exact = AutoInput(interval_s=0.5, jitter_s=0.0)
    assert exact.next_interval() == 0.5

    jittered = AutoInput(interval_s=1.0, jitter_s=0.2)
    for _ in range(200):
        v = jittered.next_interval()
        assert 0.8 - 1e-9 <= v <= 1.2 + 1e-9

    # Jitter can never drive the interval to zero/negative.
    tiny = AutoInput(interval_s=0.01, jitter_s=1.0)
    for _ in range(200):
        assert tiny.next_interval() >= 0.001


def test_store_includes_auto_inputs(tmp_path):
    autos = [AutoInput(name="a", interval_s=0.2), AutoInput(name="b", action=AUTO_CLICK)]
    path = tmp_path / "cfg.json"
    save_watchers([], [], path, autos)
    t, g, a = load_watchers(path)
    assert t == [] and g == []
    assert [x.name for x in a] == ["a", "b"]
