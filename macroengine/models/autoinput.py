"""Auto inputs: fire a single action on a repeating timer.

Unlike a recorded macro (a *sequence* replayed in order), each auto input is an
*independent repeater* — e.g. "press ``2`` every 3 s" or "left-click at (840, 512)
every 200 ms". Several can run at once, each on its own interval, with optional
random jitter so the timing isn't perfectly robotic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict

# Action kinds.
AUTO_PRESS_KEY = "press_key"   # tap a key
AUTO_CLICK = "click"           # click at a fixed screen position
AUTO_RUN_MACRO = "run_macro"   # play a saved macro once


@dataclass
class AutoInput:
    name: str = "Auto input"
    enabled: bool = True

    action: str = AUTO_PRESS_KEY
    # press_key
    key: str = "1"
    # click
    x: int = 0
    y: int = 0
    button: str = "left"
    # run_macro
    macro_path: str = ""

    interval_s: float = 1.0   # base period between fires
    jitter_s: float = 0.0     # random +/- added to each interval

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "action": self.action,
            "key": self.key,
            "x": self.x,
            "y": self.y,
            "button": self.button,
            "macro_path": self.macro_path,
            "interval_s": self.interval_s,
            "jitter_s": self.jitter_s,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "AutoInput":
        return cls(
            name=raw.get("name", "Auto input"),
            enabled=bool(raw.get("enabled", True)),
            action=raw.get("action", AUTO_PRESS_KEY),
            key=raw.get("key", "1"),
            x=int(raw.get("x", 0)),
            y=int(raw.get("y", 0)),
            button=raw.get("button", "left"),
            macro_path=raw.get("macro_path", ""),
            interval_s=float(raw.get("interval_s", 1.0)),
            jitter_s=float(raw.get("jitter_s", 0.0)),
        )

    def next_interval(self) -> float:
        """Seconds until the next fire: ``interval_s`` ± ``jitter_s`` (never <= 0)."""
        base = self.interval_s
        if self.jitter_s > 0:
            base += random.uniform(-self.jitter_s, self.jitter_s)
        return max(0.001, base)

    def describe(self) -> str:
        if self.action == AUTO_PRESS_KEY:
            what = f"press '{self.key}'"
        elif self.action == AUTO_CLICK:
            what = f"{self.button}-click ({self.x}, {self.y})"
        else:
            what = "run macro"
        every = f"every {self.interval_s:g}s"
        if self.jitter_s:
            every += f" ±{self.jitter_s:g}s"
        return f"{self.name}: {what} {every}"
