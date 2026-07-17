"""A vision trigger: a *condition* evaluated against a screen region, and an
*action* to perform when the condition holds.

The condition/action split is deliberate: a future "memory watch" cheat-engine
condition can be added as another ``detection`` kind without touching the action
side or the monitor loop.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -- detection kinds --------------------------------------------------------
DETECT_TEMPLATE = "template"  # match a reference image inside the region
DETECT_COLOR = "color"        # measure how much of the region falls in an HSV band

# -- conditions -------------------------------------------------------------
COND_PRESENT = "present"          # template: reference is visible
COND_ABSENT = "absent"            # template: reference is NOT visible (e.g. buff gone)
COND_RATIO_ABOVE = "ratio_above"  # color: matched fraction > threshold (e.g. HP bar red)
COND_RATIO_BELOW = "ratio_below"  # color: matched fraction < threshold

# -- actions (shared vocabulary; see models/actions.py) ----------------------
from .actions import (  # noqa: E402  (re-exported under the historical names)
    CLICK_AT as ACTION_CLICK_AT,
    CLICK_MATCH as ACTION_CLICK_MATCH,
    PRESS_KEY as ACTION_PRESS_KEY,
    RUN_MACRO as ACTION_RUN_MACRO,
    TYPE_TEXT as ACTION_TYPE_TEXT,
    describe_action,
)

FILE_FORMAT = "macroengine.triggers"
FILE_VERSION = 1


@dataclass
class Trigger:
    name: str = "Trigger"
    enabled: bool = True

    # Screen region to watch: (x, y, width, height) in screen pixels.
    region: Tuple[int, int, int, int] = (0, 0, 100, 100)

    # Detection configuration.
    detection: str = DETECT_TEMPLATE
    # template mode: PNG bytes of the reference snippet (base64 in JSON) + match score.
    template_png: Optional[bytes] = None
    match_threshold: float = 0.8
    # color mode: inclusive HSV bounds (OpenCV ranges: H 0-179, S/V 0-255).
    hsv_lower: Tuple[int, int, int] = (0, 100, 100)
    hsv_upper: Tuple[int, int, int] = (10, 255, 255)

    # Condition to fire on.
    condition: str = COND_ABSENT
    ratio_threshold: float = 0.2  # used by ratio_above / ratio_below

    # Action to perform (shared vocabulary), and how often it may fire.
    action: str = ACTION_PRESS_KEY
    action_key: str = "1"           # press_key: keystroke spec
    action_text: str = ""           # type_text: literal string
    action_x: int = 0               # click_at: fixed screen position
    action_y: int = 0
    action_button: str = "left"
    action_macro_path: str = ""     # run_macro
    cooldown_s: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "region": list(self.region),
            "detection": self.detection,
            "template_png": base64.b64encode(self.template_png).decode("ascii")
            if self.template_png
            else None,
            "match_threshold": self.match_threshold,
            "hsv_lower": list(self.hsv_lower),
            "hsv_upper": list(self.hsv_upper),
            "condition": self.condition,
            "ratio_threshold": self.ratio_threshold,
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
    def from_dict(cls, raw: Dict[str, Any]) -> "Trigger":
        tpl = raw.get("template_png")
        return cls(
            name=raw.get("name", "Trigger"),
            enabled=bool(raw.get("enabled", True)),
            region=tuple(raw.get("region", (0, 0, 100, 100))),  # type: ignore[arg-type]
            detection=raw.get("detection", DETECT_TEMPLATE),
            template_png=base64.b64decode(tpl) if tpl else None,
            match_threshold=float(raw.get("match_threshold", 0.8)),
            hsv_lower=tuple(raw.get("hsv_lower", (0, 100, 100))),  # type: ignore[arg-type]
            hsv_upper=tuple(raw.get("hsv_upper", (10, 255, 255))),  # type: ignore[arg-type]
            condition=raw.get("condition", COND_ABSENT),
            ratio_threshold=float(raw.get("ratio_threshold", 0.2)),
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
        if self.detection == DETECT_TEMPLATE:
            det = f"template {self.condition} (>= {self.match_threshold:.2f})"
        else:
            det = f"color {self.condition} {self.ratio_threshold:.2f}"
        act = describe_action(
            self.action, key=self.action_key, text=self.action_text,
            x=self.action_x, y=self.action_y, button=self.action_button,
            macro_path=self.action_macro_path,
        )
        return f"{det} -> {act}"


def save_triggers(triggers: List[Trigger], path: str | Path) -> None:
    payload = {
        "format": FILE_FORMAT,
        "version": FILE_VERSION,
        "triggers": [t.to_dict() for t in triggers],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_triggers(path: str | Path) -> List[Trigger]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Trigger.from_dict(t) for t in raw.get("triggers", [])]
