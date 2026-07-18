"""Tests for settings persistence and hotkey-name conversion."""

from macroengine import config
from macroengine.config import event_names_for, hotkey_to_event_name


def test_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "a"))
    monkeypatch.setattr(type(tmp_path), "home", classmethod(lambda cls: tmp_path / "h"))
    s = config.load_settings()
    assert s["record_hotkey"] == "<f9>"
    assert s["countdown_s"] == 0
    assert s["overlay_enabled"] is True


def test_roundtrip_and_unknown_keys_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "a"))
    monkeypatch.setattr(type(tmp_path), "home", classmethod(lambda cls: tmp_path / "h"))
    s = config.load_settings()
    s["record_hotkey"] = "<f6>"
    s["countdown_s"] = 3
    s["window"] = [10, 20, 800, 600]
    s["bogus"] = "ignored"
    config.save_settings(s)

    again = config.load_settings()
    assert again["record_hotkey"] == "<f6>"
    assert again["countdown_s"] == 3
    assert again["window"] == [10, 20, 800, 600]
    assert "bogus" not in again  # unknown keys are dropped


def test_corrupt_file_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "a"))
    monkeypatch.setattr(type(tmp_path), "home", classmethod(lambda cls: tmp_path / "h"))
    config.settings_file().write_text("{not json", encoding="utf-8")
    assert config.load_settings()["record_hotkey"] == "<f9>"


def test_hotkey_to_event_name():
    assert hotkey_to_event_name("<f9>") == "Key.f9"
    assert hotkey_to_event_name("<esc>") == "Key.esc"
    assert hotkey_to_event_name("<scroll_lock>") == "Key.scroll_lock"
    assert event_names_for("<f9>", "<f10>", "<esc>") == {"Key.f9", "Key.f10", "Key.esc"}
