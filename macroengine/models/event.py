"""A single recorded input event.

Events are the atoms of a macro. Every event carries a ``delay`` — the number of
seconds to wait *after the previous event* before this one is performed — so that
playback reproduces the original timing regardless of absolute timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

# Supported event types.
KEY_DOWN = "key_down"
KEY_UP = "key_up"
MOUSE_MOVE = "mouse_move"
MOUSE_CLICK = "mouse_click"
MOUSE_SCROLL = "mouse_scroll"

EVENT_TYPES = (KEY_DOWN, KEY_UP, MOUSE_MOVE, MOUSE_CLICK, MOUSE_SCROLL)


@dataclass
class Event:
    """One input action.

    ``data`` payload by type:
      * key_down / key_up  -> {"key": "<name>"}
      * mouse_move         -> {"x": int, "y": int}
      * mouse_click        -> {"x": int, "y": int, "button": "left|right|middle",
                               "pressed": bool}
      * mouse_scroll       -> {"x": int, "y": int, "dx": int, "dy": int}
    """

    type: str
    delay: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"Unknown event type: {self.type!r}")
        if self.delay < 0:
            self.delay = 0.0

    # -- human-readable description used by the editable table --------------
    def describe(self) -> str:
        d = self.data
        if self.type == KEY_DOWN:
            return f"Key down: {d.get('key', '?')}"
        if self.type == KEY_UP:
            return f"Key up: {d.get('key', '?')}"
        if self.type == MOUSE_MOVE:
            return f"Move to ({d.get('x', '?')}, {d.get('y', '?')})"
        if self.type == MOUSE_CLICK:
            state = "press" if d.get("pressed") else "release"
            return f"Mouse {state} {d.get('button', '?')} at ({d.get('x', '?')}, {d.get('y', '?')})"
        if self.type == MOUSE_SCROLL:
            return f"Scroll ({d.get('dx', 0)}, {d.get('dy', 0)}) at ({d.get('x', '?')}, {d.get('y', '?')})"
        return self.type

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "delay": round(self.delay, 4), "data": dict(self.data)}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Event":
        return cls(
            type=raw["type"],
            delay=float(raw.get("delay", 0.0)),
            data=dict(raw.get("data", {})),
        )
