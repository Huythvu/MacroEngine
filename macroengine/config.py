"""Persisted application settings (``settings.json`` in the per-user data dir).

Loading is defensive: a missing or corrupt file yields the defaults, and unknown
keys are ignored, so upgrades and hand-edits never crash the app.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .paths import app_data_dir

DEFAULTS: Dict[str, Any] = {
    "record_hotkey": "<f9>",
    "play_hotkey": "<f10>",
    "panic_hotkey": "<esc>",
    "countdown_s": 0,          # 0 = start immediately (button-initiated only)
    "overlay_enabled": True,   # show the on-screen status overlay
    "record_mouse_moves": True,
    "window": None,            # [x, y, w, h] or None
    "show_library": True,      # Recorder's "Saved macros" side panel visible
    "show_activity_log": True, # Activity log dock visible
}


def settings_file():
    return app_data_dir() / "settings.json"


# -- hotkey helpers (pure; kept here so they import without pynput) ----------
def hotkey_to_event_name(spec: str) -> str:
    """Convert a pynput hotkey spec (``"<f9>"``) to the recorder's key name
    (``"Key.f9"``) so configured hotkeys can be excluded from recordings."""
    name = spec.strip().strip("<>")
    return f"Key.{name}" if name else ""


def event_names_for(*specs: str):
    return frozenset(n for n in (hotkey_to_event_name(s) for s in specs) if n)


# Choices the settings dialog offers (pynput hotkey syntax).
HOTKEY_CHOICES = (
    [f"<f{i}>" for i in range(1, 13)]
    + ["<esc>", "<pause>", "<scroll_lock>", "<insert>", "<home>", "<end>",
       "<page_up>", "<page_down>", "<print_screen>"]
)


def load_settings() -> Dict[str, Any]:
    data = dict(DEFAULTS)
    try:
        raw = json.loads(settings_file().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key in DEFAULTS:
                if key in raw:
                    data[key] = raw[key]
    except Exception:  # noqa: BLE001  (missing/corrupt -> defaults)
        pass
    return data


def save_settings(data: Dict[str, Any]) -> None:
    # Only persist known keys.
    payload = {k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}
    try:
        settings_file().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
