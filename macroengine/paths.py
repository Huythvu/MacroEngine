"""Per-user data locations (writable), separate from bundled resources.

The routines library lives here so saved routines persist across runs and show
up in the Routine tab.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    """Writable per-user data dir, created on demand.

    Windows: ``%APPDATA%/MacroEngine``; otherwise ``~/.macroengine``.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home())
        path = Path(base) / "MacroEngine"
    else:
        path = Path.home() / ".macroengine"
    path.mkdir(parents=True, exist_ok=True)
    return path


def routines_dir() -> Path:
    """Folder holding the saved-routine library (``*.json``)."""
    path = app_data_dir() / "routines"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    """Turn a routine name into a safe file stem."""
    keep = "".join(c if (c.isalnum() or c in " -_.") else "_" for c in name).strip()
    return keep or "routine"
