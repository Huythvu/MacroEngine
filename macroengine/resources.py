"""Locating bundled resources (icons) in both a dev checkout and a PyInstaller
one-file build.

PyInstaller unpacks bundled data to ``sys._MEIPASS`` at runtime; in a dev
checkout the assets live at the repo root next to the ``macroengine`` package.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


def _base_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:  # frozen (PyInstaller)
        return Path(meipass)
    # dev: macroengine/resources.py -> repo root
    return Path(__file__).resolve().parent.parent


def app_icon_path() -> Optional[str]:
    """Best available window icon, or ``None`` if none is bundled.

    Prefers the generated multi-size .ico, then the raw source image.
    """
    base = _base_dir()
    for rel in ("assets/MacroEngine.ico", "assets/icon_source.png"):
        path = base / rel
        if path.exists():
            return str(path)
    return None
