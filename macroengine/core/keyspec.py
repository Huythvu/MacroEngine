"""Keystroke specs for action keys (triggers, buff items, auto inputs).

A *keystroke spec* is a human-friendly string describing one keypress, possibly
with modifiers:

    "a"              a single letter
    "1"              a digit
    "esc"            a named special key
    "ctrl+c"         a combo (modifiers held while the main key is tapped)
    "ctrl+shift+a"   multiple modifiers
    "alt"            a lone modifier (press+release Alt by itself)

This replaces the old single-character handling, which could only send one plain
key — so special keys (Alt/Ctrl/Esc/Backspace…) and combos were unreachable, and a
multi-character value like ``"123asd"`` silently sent just ``"1"``.

``split_spec`` is pure (no pynput) and unit-tested; resolution/sending needs a
pynput keyboard Controller.
"""

from __future__ import annotations

from typing import List, Tuple

# Normalize common spellings to pynput ``keyboard.Key`` attribute names.
ALIASES = {
    "control": "ctrl",
    "ctl": "ctrl",
    "escape": "esc",
    "return": "enter",
    "del": "delete",
    "ins": "insert",
    "win": "cmd",
    "super": "cmd",
    "meta": "cmd",
    "windows": "cmd",
    "altgr": "alt_gr",
    "spacebar": "space",
    "pgup": "page_up",
    "pageup": "page_up",
    "pgdn": "page_down",
    "pgdown": "page_down",
    "pagedown": "page_down",
    "capslock": "caps_lock",
    "numlock": "num_lock",
    "scrolllock": "scroll_lock",
    "printscreen": "print_screen",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
}

MODIFIER_TOKENS = frozenset({"ctrl", "alt", "shift", "cmd", "alt_gr", "ctrl_l", "ctrl_r",
                             "alt_l", "alt_r", "shift_l", "shift_r"})

# Valid pynput ``keyboard.Key`` names, hardcoded so resolvability can be decided
# without importing pynput (keeps the type-vs-press decision unit-testable).
_KEY_NAMES = frozenset(
    {
        "alt", "alt_gr", "alt_l", "alt_r", "backspace", "caps_lock", "cmd",
        "cmd_l", "cmd_r", "ctrl", "ctrl_l", "ctrl_r", "delete", "down", "end",
        "enter", "esc", "home", "insert", "left", "menu", "num_lock",
        "page_down", "page_up", "pause", "print_screen", "right", "scroll_lock",
        "shift", "shift_l", "shift_r", "space", "tab", "up",
    }
    | {f"f{i}" for i in range(1, 25)}
)


def is_resolvable(token: str) -> bool:
    """True if ``token`` names a single key (a char or a known special-key name).

    Pure — used to decide whether a spec should be *typed as text* instead of
    pressed (e.g. an old ``"123asd"`` value).
    """
    return len(token) == 1 or token in _KEY_NAMES


def normalize_token(token: str) -> str:
    t = token.strip().lower()
    return ALIASES.get(t, t)


def split_spec(spec: str) -> Tuple[List[str], str]:
    """Split a spec into ``(modifier_tokens, main_token)``.

    Tokens are normalized (lower-cased, aliases applied). The last token is the
    main key; any preceding tokens are modifiers. A lone modifier (``"alt"``)
    yields no modifier prefixes and ``"alt"`` as the main key. An empty spec
    yields ``([], "")``.
    """
    parts = [normalize_token(p) for p in spec.split("+") if p.strip()]
    if not parts:
        return ([], "")
    return (parts[:-1], parts[-1])


def _resolve(token: str):
    """Token -> a pynput key object, or ``None`` if it isn't a single key."""
    from pynput import keyboard

    if len(token) == 1:
        return keyboard.KeyCode.from_char(token)
    key = getattr(keyboard.Key, token, None)
    return key  # may be None for unknown multi-char tokens


def press_keystroke(kbd, spec: str) -> None:
    """Send one keystroke described by ``spec`` using a pynput Controller.

    If the main token cannot be resolved to a key and there are no modifiers
    (e.g. an old ``"123asd"`` value), the literal string is *typed* instead of
    silently dropping all but the first character.
    """
    spec = (spec or "").strip()
    if not spec:
        return
    mods, main = split_spec(spec)
    # Decide purely (no pynput) whether this is a real keystroke or literal text.
    if not is_resolvable(main) and not mods:
        kbd.type(spec)  # graceful fallback: type the literal text
        return
    main_key = _resolve(main)
    mod_keys = [k for k in (_resolve(m) for m in mods) if k is not None]
    try:
        for m in mod_keys:
            kbd.press(m)
        if main_key is not None:
            kbd.press(main_key)
            kbd.release(main_key)
    finally:
        for m in reversed(mod_keys):
            kbd.release(m)


def type_text(kbd, text: str) -> None:
    """Type a whole string (each character in turn) via a pynput Controller."""
    if text:
        kbd.type(text)
