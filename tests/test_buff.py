"""Tests for buff groups: model round-trip, detection, and persistence."""

import json

import numpy as np

from macroengine.models.buff import BuffGroup, BuffItem
from macroengine.models.store import load_watchers, save_watchers
from macroengine.models.trigger import COND_ABSENT, COND_PRESENT, Trigger
from macroengine.vision import detector


def _solid(h, w, bgr):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = bgr
    return img


def _textured(h, w, seed):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def test_buffgroup_roundtrip():
    group = BuffGroup(
        name="bar",
        region=(10, 20, 300, 40),
        items=[
            BuffItem(name="haste", template_png=b"\x89PNGa", condition=COND_ABSENT, action_key="1"),
            BuffItem(name="shield", template_png=b"\x89PNGb", condition=COND_PRESENT, action_key="2"),
        ],
    )
    restored = BuffGroup.from_dict(group.to_dict())
    assert restored.name == "bar"
    assert restored.region == (10, 20, 300, 40)
    assert len(restored.items) == 2
    assert restored.items[0].name == "haste"
    assert restored.items[0].template_png == b"\x89PNGa"
    assert restored.items[1].condition == COND_PRESENT


def test_template_present_scores():
    icon = _textured(12, 12, seed=3)
    bar = _solid(40, 200, (0, 0, 0))
    bar[10:22, 80:92] = icon  # place the icon somewhere in the bar
    png = detector.encode_png(icon)
    present, score = detector.template_present(bar, png, 0.8)
    assert present and score > 0.95

    empty = _textured(40, 200, seed=50)
    present2, score2 = detector.template_present(empty, png, 0.8)
    assert not present2


def test_buff_item_met_absent_and_present():
    icon = _textured(12, 12, seed=9)
    png = detector.encode_png(icon)
    bar_with = _solid(40, 200, (0, 0, 0))
    bar_with[5:17, 30:42] = icon
    bar_without = _textured(40, 200, seed=99)

    absent = BuffItem(template_png=png, condition=COND_ABSENT, match_threshold=0.8)
    present = BuffItem(template_png=png, condition=COND_PRESENT, match_threshold=0.8)

    # Buff visible: absent-condition should NOT fire; present-condition should.
    assert detector.buff_item_met(present, bar_with)[0] is True
    assert detector.buff_item_met(absent, bar_with)[0] is False
    # Buff gone: absent-condition fires; present-condition does not.
    assert detector.buff_item_met(absent, bar_without)[0] is True
    assert detector.buff_item_met(present, bar_without)[0] is False


def test_store_roundtrip_and_backcompat(tmp_path):
    triggers = [Trigger(name="hp")]
    groups = [BuffGroup(name="buffs", items=[BuffItem(name="a", template_png=b"x")])]
    path = tmp_path / "w.json"
    save_watchers(triggers, groups, path)
    t2, g2 = load_watchers(path)
    assert len(t2) == 1 and t2[0].name == "hp"
    assert len(g2) == 1 and g2[0].items[0].name == "a"

    # Old trigger-only file (no buff_groups key) still loads, with empty groups.
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({
        "format": "macroengine.triggers", "version": 1,
        "triggers": [Trigger(name="old").to_dict()],
    }), encoding="utf-8")
    t3, g3 = load_watchers(legacy)
    assert len(t3) == 1 and t3[0].name == "old"
    assert g3 == []
