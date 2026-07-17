"""Tests for keystroke parsing/sending and the Type-text auto action."""

import pytest

from macroengine.core import keyspec
from macroengine.models.autoinput import AUTO_TYPE_TEXT, AutoInput


# -- split_spec (pure) --------------------------------------------------------

def test_split_single_key():
    assert keyspec.split_spec("a") == ([], "a")
    assert keyspec.split_spec("1") == ([], "1")


def test_split_lone_modifier():
    assert keyspec.split_spec("alt") == ([], "alt")


def test_split_combo():
    assert keyspec.split_spec("ctrl+c") == (["ctrl"], "c")
    assert keyspec.split_spec("ctrl+shift+a") == (["ctrl", "shift"], "a")


def test_split_normalizes_aliases_and_case():
    assert keyspec.split_spec("CONTROL+C") == (["ctrl"], "c")
    assert keyspec.split_spec("Escape") == ([], "esc")
    assert keyspec.split_spec("win+d") == (["cmd"], "d")
    assert keyspec.split_spec("ALT+F4") == (["alt"], "f4")


def test_split_empty():
    assert keyspec.split_spec("") == ([], "")
    assert keyspec.split_spec("   ") == ([], "")


def test_is_resolvable():
    assert keyspec.is_resolvable("a")       # single char
    assert keyspec.is_resolvable("1")
    assert keyspec.is_resolvable("esc")     # known special key
    assert keyspec.is_resolvable("f4")
    assert not keyspec.is_resolvable("123asd")   # multi-char, not a key name
    assert not keyspec.is_resolvable("nope")


# -- press_keystroke / type_text against a fake controller --------------------

class FakeKbd:
    """Records the sequence of press/release/type calls."""

    def __init__(self):
        self.calls = []

    def press(self, k):
        self.calls.append(("press", k))

    def release(self, k):
        self.calls.append(("release", k))

    def type(self, text):
        self.calls.append(("type", text))


# Resolving real keys needs pynput (single-key / combo sequencing).
def test_press_single_key_presses_and_releases():
    pytest.importorskip("pynput")
    kbd = FakeKbd()
    keyspec.press_keystroke(kbd, "a")
    assert [c[0] for c in kbd.calls] == ["press", "release"]


def test_press_combo_holds_then_releases_modifier():
    pytest.importorskip("pynput")
    kbd = FakeKbd()
    keyspec.press_keystroke(kbd, "ctrl+c")
    kinds = [c[0] for c in kbd.calls]
    # modifier pressed first, released last
    assert kinds == ["press", "press", "release", "release"]


def test_press_unresolvable_multichar_types_literal():
    # Old-style "123asd" in a press-key field must type the whole string,
    # not silently send just "1".
    kbd = FakeKbd()
    keyspec.press_keystroke(kbd, "123asd")
    assert kbd.calls == [("type", "123asd")]


def test_press_empty_does_nothing():
    kbd = FakeKbd()
    keyspec.press_keystroke(kbd, "")
    assert kbd.calls == []


def test_type_text():
    kbd = FakeKbd()
    keyspec.type_text(kbd, "hello")
    assert kbd.calls == [("type", "hello")]
    kbd2 = FakeKbd()
    keyspec.type_text(kbd2, "")
    assert kbd2.calls == []


# -- model round-trip ---------------------------------------------------------

def test_type_text_autoinput_roundtrip():
    a = AutoInput(name="chat", action=AUTO_TYPE_TEXT, text="123asd", interval_s=2.0)
    restored = AutoInput.from_dict(a.to_dict())
    assert restored.action == AUTO_TYPE_TEXT
    assert restored.text == "123asd"
