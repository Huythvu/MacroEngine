"""Buff groups: watch one screen region (a buff bar) for several icons at once.

Because a buff icon is matched *anywhere* inside the group's region (see
``vision.detector.template_match``), this handles buff bars where icons shift or
reorder as buffs expire — you only need the icon, not its fixed position.

A :class:`BuffGroup` owns the shared region and a list of :class:`BuffItem`, each
of which is one buff to look for, with its own present/absent condition and action.
The item reuses the same condition/action vocabulary as :class:`~.trigger.Trigger`.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .actions import describe_action
from .trigger import (
    ACTION_PRESS_KEY,
    COND_ABSENT,
)


@dataclass
class BuffItem:
    name: str = "Buff"
    enabled: bool = True
    # Reference icon (PNG bytes; base64 in JSON) searched for within the group region.
    template_png: Optional[bytes] = None
    match_threshold: float = 0.8
    # COND_PRESENT (fire when the buff is visible) or COND_ABSENT (fire when it's gone).
    condition: str = COND_ABSENT
    # Action when the condition holds (shared vocabulary; see models/actions.py).
    action: str = ACTION_PRESS_KEY
    action_key: str = "1"
    action_text: str = ""
    action_x: int = 0
    action_y: int = 0
    action_button: str = "left"
    action_macro_path: str = ""
    cooldown_s: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "template_png": base64.b64encode(self.template_png).decode("ascii")
            if self.template_png
            else None,
            "match_threshold": self.match_threshold,
            "condition": self.condition,
            "action": self.action,
            "action_key": self.action_key,
            "action_text": self.action_text,
            "action_x": self.action_x,
            "action_y": self.action_y,
            "action_button": self.action_button,
            "action_macro_path": self.action_macro_path,
            "cooldown_s": self.cooldown_s,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "BuffItem":
        tpl = raw.get("template_png")
        return cls(
            name=raw.get("name", "Buff"),
            enabled=bool(raw.get("enabled", True)),
            template_png=base64.b64decode(tpl) if tpl else None,
            match_threshold=float(raw.get("match_threshold", 0.8)),
            condition=raw.get("condition", COND_ABSENT),
            action=raw.get("action", ACTION_PRESS_KEY),
            action_key=raw.get("action_key", "1"),
            action_text=raw.get("action_text", ""),
            action_x=int(raw.get("action_x", 0)),
            action_y=int(raw.get("action_y", 0)),
            action_button=raw.get("action_button", "left"),
            action_macro_path=raw.get("action_macro_path", ""),
            cooldown_s=float(raw.get("cooldown_s", 1.0)),
        )

    def describe(self) -> str:
        act = describe_action(
            self.action, key=self.action_key, text=self.action_text,
            x=self.action_x, y=self.action_y, button=self.action_button,
            macro_path=self.action_macro_path,
        )
        return f"{self.name}: {self.condition} -> {act}"


@dataclass
class BuffGroup:
    name: str = "Buff group"
    enabled: bool = True
    # Shared region to watch: (x, y, width, height) in screen pixels — the buff bar.
    region: Tuple[int, int, int, int] = (0, 0, 200, 60)
    items: List[BuffItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "region": list(self.region),
            "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "BuffGroup":
        return cls(
            name=raw.get("name", "Buff group"),
            enabled=bool(raw.get("enabled", True)),
            region=tuple(raw.get("region", (0, 0, 200, 60))),  # type: ignore[arg-type]
            items=[BuffItem.from_dict(i) for i in raw.get("items", [])],
        )

    def describe(self) -> str:
        return f"{self.name} — {len(self.items)} buff(s)"
