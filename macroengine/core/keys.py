"""Helpers to convert between pynput key/button objects and portable strings.

Recorded macros must survive a round-trip through JSON, so every key and mouse
button is stored as a plain string:

  * special keys  -> ``"Key.enter"``, ``"Key.space"`` ...
  * character keys -> the character itself, e.g. ``"a"``, ``"1"``, ``" "``
  * mouse buttons  -> ``"left"`` / ``"right"`` / ``"middle"``
"""

from __future__ import annotations

from typing import Any

from pynput import keyboard, mouse


def key_to_name(key: Any) -> str:
    """Convert a pynput key (from a listener callback) to a portable string."""
    # KeyCode with a printable character.
    char = getattr(key, "char", None)
    if char is not None:
        return char
    # Special Key enum member -> "Key.enter" etc.
    if isinstance(key, keyboard.Key):
        return str(key)  # e.g. "Key.enter"
    # KeyCode without a char but with a virtual key code.
    vk = getattr(key, "vk", None)
    if vk is not None:
        return f"vk:{vk}"
    return str(key)


def name_to_key(name: str) -> Any:
    """Convert a stored string back into something a Controller can press."""
    if name.startswith("Key."):
        return getattr(keyboard.Key, name[4:])
    if name.startswith("vk:"):
        return keyboard.KeyCode.from_vk(int(name[3:]))
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    # Fallback: try to interpret as a special key name (e.g. "enter").
    special = getattr(keyboard.Key, name, None)
    if special is not None:
        return special
    return keyboard.KeyCode.from_char(name[0]) if name else keyboard.Key.space


def button_to_name(button: Any) -> str:
    return button.name  # Button.left -> "left"


def name_to_button(name: str) -> Any:
    return getattr(mouse.Button, name, mouse.Button.left)
