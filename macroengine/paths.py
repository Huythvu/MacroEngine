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


def macros_dir() -> Path:
    """Folder holding the saved-macro library (``*.json``)."""
    path = app_data_dir() / "macros"
    path.mkdir(parents=True, exist_ok=True)
    return path


def watchers_file() -> Path:
    """The auto-saved watchers session (triggers + buff groups + auto inputs)."""
    return app_data_dir() / "watchers.json"


def safe_filename(name: str) -> str:
    """Turn a routine name into a safe file stem."""
    keep = "".join(c if (c.isalnum() or c in " -_.()") else "_" for c in name).strip()
    return keep or "routine"


def unique_name(directory: Path, name: str, exclude: Path | None = None) -> str:
    """Return ``name``, or ``name(1)`` / ``name(2)`` … if a ``*.json`` already
    exists for it — the same way Windows disambiguates a duplicate file name.

    ``exclude`` is a path to ignore (the file we're re-saving over, so editing an
    open routine keeps its own name instead of bumping to ``(1)``).
    """
    directory.mkdir(parents=True, exist_ok=True)

    def taken(candidate: str) -> bool:
        path = directory / f"{safe_filename(candidate)}.json"
        return path.exists() and path != exclude

    if not taken(name):
        return name
    i = 1
    while taken(f"{name}({i})"):
        i += 1
    return f"{name}({i})"
