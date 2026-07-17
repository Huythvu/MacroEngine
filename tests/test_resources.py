"""Tests for bundled-resource path resolution (dev + frozen)."""

import sys

from macroengine import resources


def test_prefers_ico_then_png(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "icon_source.png").write_bytes(b"x")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    # Only the png exists -> it is used.
    assert resources.app_icon_path() == str(assets / "icon_source.png")

    # Once the .ico exists it wins.
    (assets / "MacroEngine.ico").write_bytes(b"y")
    assert resources.app_icon_path() == str(assets / "MacroEngine.ico")


def test_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)  # no assets/
    assert resources.app_icon_path() is None
