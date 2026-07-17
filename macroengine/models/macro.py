"""A macro: an ordered list of :class:`Event` plus loop configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .event import Event

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
        return cls.from_dict(raw)
