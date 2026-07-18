"""The unified action vocabulary shared by triggers, buff items, and auto inputs.

Every "when X happens, do Y" feature draws from the same set of actions, so the
same action editor UI serves all of them. String values are kept identical to
the older per-model constants (``ACTION_*`` in trigger.py, ``AUTO_*`` in
autoinput.py) so existing saved files load unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

NONE = "none"                # do nothing
PRESS_KEY = "press_key"      # tap a key or combo (e.g. "a", "esc", "ctrl+c")
TYPE_TEXT = "type_text"      # type a whole string
CLICK_AT = "click"           # click at a fixed screen position
CLICK_MATCH = "click_match"  # click where the template was found (needs a template)
RUN_MACRO = "run_macro"      # play a saved macro once

ALL_ACTIONS = (PRESS_KEY, TYPE_TEXT, CLICK_AT, CLICK_MATCH, RUN_MACRO)

# Human labels for the shared action editor.
LABELS = {
    NONE: "Do nothing",
    PRESS_KEY: "Press key / combo",
    TYPE_TEXT: "Type text",
    CLICK_AT: "Click at position",
    CLICK_MATCH: "Click on the found image",
    RUN_MACRO: "Run macro",
}


@dataclass
class Action:
    """A self-contained action (used where a step needs an embedded action, e.g.
    the then/else branches of an If-vision step)."""

    kind: str = NONE
    key: str = "1"
    text: str = ""
    x: int = 0
    y: int = 0
    button: str = "left"
    macro_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind, "key": self.key, "text": self.text,
            "x": self.x, "y": self.y, "button": self.button,
            "macro_path": self.macro_path,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Action":
        raw = raw or {}
        return cls(
            kind=raw.get("kind", NONE),
            key=raw.get("key", "1"),
            text=raw.get("text", ""),
            x=int(raw.get("x", 0)),
            y=int(raw.get("y", 0)),
            button=raw.get("button", "left"),
            macro_path=raw.get("macro_path", ""),
        )

    def describe(self) -> str:
        return describe_action(
            self.kind, key=self.key, text=self.text, x=self.x, y=self.y,
            button=self.button, macro_path=self.macro_path,
        )


def describe_action(action: str, key: str = "", text: str = "", x: int = 0,
                    y: int = 0, button: str = "left", macro_path: str = "") -> str:
    """Short human description of an action, for list rows."""
    from pathlib import Path

    if action == NONE:
        return "do nothing"
    if action == PRESS_KEY:
        return f"press '{key}'"
    if action == TYPE_TEXT:
        preview = text if len(text) <= 20 else text[:17] + "…"
        return f"type '{preview}'"
    if action == CLICK_AT:
        return f"{button}-click ({x}, {y})"
    if action == CLICK_MATCH:
        return "click the found image"
    if action == RUN_MACRO:
        return f"run {Path(macro_path).name or '<macro>'}"
    return action
