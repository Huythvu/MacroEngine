"""A macro: an ordered list of :class:`Event` plus loop configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .event import MOUSE_CLICK, Event


def trim_edge_clicks(
    events: List[Event], leading: bool = True, trailing: bool = True
) -> List[Event]:
    """Strip the junk clicks recorded when recording is started/stopped via the
    app's own Record button (audit bug #4): those clicks land on MacroEngine
    itself, so replays would click on the app window.

    ``leading``/``trailing`` correspond to recording having been *started* /
    *stopped* via the button — only trim the edge where junk can exist, so a
    macro that genuinely begins or ends with a click is never mangled.
    Conservative by design — removes at most one click press/release pair (or a
    lone half-pair) per edge, and never touches keys, moves, or scrolls.
    """
    out = list(events)

    def _is_click(ev: Event, pressed: bool) -> bool:
        return ev.type == MOUSE_CLICK and bool(ev.data.get("pressed")) is pressed

    # Leading: a press+release pair, or a lone release (the press of the click
    # that started recording can land before the listeners are up).
    if leading:
        if len(out) >= 2 and _is_click(out[0], True) and _is_click(out[1], False):
            out = out[2:]
        elif out and _is_click(out[0], False):
            out = out[1:]

    # Trailing: a press+release pair, or a lone press (its release arrives after
    # the listeners stop).
    if trailing:
        if len(out) >= 2 and _is_click(out[-2], True) and _is_click(out[-1], False):
            out = out[:-2]
        elif out and _is_click(out[-1], True):
            out = out[:-1]

    return out

FILE_FORMAT = "macroengine.macro"
FILE_VERSION = 1


@dataclass
class Macro:
    """A recorded sequence of input events.

    ``loop_count`` == 0 means "loop forever" (until the panic hotkey is pressed).
    """

    name: str = "Untitled"
    events: List[Event] = field(default_factory=list)
    loop_count: int = 1

    # -- convenience --------------------------------------------------------
    def duration(self) -> float:
        """Total time (seconds) for a single pass through the events."""
        return sum(e.delay for e in self.events)

    def clear(self) -> None:
        self.events.clear()

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": FILE_FORMAT,
            "version": FILE_VERSION,
            "name": self.name,
            "loop_count": self.loop_count,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Macro":
        return cls(
            name=raw.get("name", "Untitled"),
            loop_count=int(raw.get("loop_count", 1)),
            events=[Event.from_dict(e) for e in raw.get("events", [])],
        )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Macro":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        # TODO(audit): no format check — loading a watchers.json here yields a
        # silently-empty macro. Validate raw.get("format") == FILE_FORMAT and
        # raise a clear error naming the actual format found.
        return cls.from_dict(raw)
