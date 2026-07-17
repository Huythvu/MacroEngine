"""Routines: chain small recorded macros with waits and vision checks.

A :class:`Routine` is an ordered list of :class:`RoutineStep`:

  * ``macro``       — play a saved macro file (a recorded "section" of a daily)
  * ``wait``        — pause N seconds (± jitter) before the next step
  * ``wait_vision`` — poll a screen region until a condition holds (icon
                      present/absent, color ratio), with a per-step timeout that
                      either stops the routine or lets it continue

Macro steps reference macro *files by path*, so re-recording a section
automatically updates every routine that uses it.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .trigger import (
    COND_ABSENT,
    DETECT_TEMPLATE,
    Trigger,
)

STEP_MACRO = "macro"
STEP_WAIT = "wait"
STEP_WAIT_VISION = "wait_vision"

TIMEOUT_STOP = "stop"          # timeout aborts the whole routine
TIMEOUT_CONTINUE = "continue"  # timeout falls through to the next step

FILE_FORMAT = "macroengine.routine"
FILE_VERSION = 1


@dataclass
class RoutineStep:
    type: str = STEP_MACRO
    enabled: bool = True
    name: str = ""

    # -- macro step ---------------------------------------------------------
    macro_path: str = ""
    loop_override: int = 0  # 0 = play the macro as saved

    # -- wait step ----------------------------------------------------------
    wait_s: float = 1.0
    jitter_s: float = 0.0

    # -- wait_vision step (same detection vocabulary as Trigger) ------------
    region: Tuple[int, int, int, int] = (0, 0, 100, 100)
    detection: str = DETECT_TEMPLATE
    template_png: Optional[bytes] = None
    match_threshold: float = 0.8
    hsv_lower: Tuple[int, int, int] = (0, 100, 100)
    hsv_upper: Tuple[int, int, int] = (10, 255, 255)
    condition: str = COND_ABSENT
    ratio_threshold: float = 0.2
    timeout_s: float = 30.0  # 0 = wait forever
    on_timeout: str = TIMEOUT_STOP

    def to_trigger(self) -> Trigger:
        """Bridge to :class:`Trigger` so the runner and the dialog's Test button
        evaluate vision steps with the exact same detector code path."""
        return Trigger(
            name=self.name or "vision step",
            region=self.region,
            detection=self.detection,
            template_png=self.template_png,
            match_threshold=self.match_threshold,
            hsv_lower=self.hsv_lower,
            hsv_upper=self.hsv_upper,
            condition=self.condition,
            ratio_threshold=self.ratio_threshold,
        )

    def describe(self) -> str:
        if self.type == STEP_MACRO:
            base = Path(self.macro_path).name or "<macro>"
            loops = f" ×{self.loop_override}" if self.loop_override > 0 else ""
            return f"Play {base}{loops}"
        if self.type == STEP_WAIT:
            jit = f" ±{self.jitter_s:g}s" if self.jitter_s else ""
            return f"Wait {self.wait_s:g}s{jit}"
        if self.type == STEP_WAIT_VISION:
            timeout = "forever" if self.timeout_s <= 0 else f"{self.timeout_s:g}s"
            after = "stop" if self.on_timeout == TIMEOUT_STOP else "continue"
            what = self.name or f"{self.detection} {self.condition}"
            return f"Wait until {what} (timeout {timeout} → {after})"
        return self.type

    def label(self) -> str:
        return self.name or self.describe()

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "enabled": self.enabled,
            "name": self.name,
            "macro_path": self.macro_path,
            "loop_override": self.loop_override,
            "wait_s": self.wait_s,
            "jitter_s": self.jitter_s,
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
            "timeout_s": self.timeout_s,
            "on_timeout": self.on_timeout,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "RoutineStep":
        tpl = raw.get("template_png")
        return cls(
            type=raw.get("type", STEP_MACRO),
            enabled=bool(raw.get("enabled", True)),
            name=raw.get("name", ""),
            macro_path=raw.get("macro_path", ""),
            loop_override=int(raw.get("loop_override", 0)),
            wait_s=float(raw.get("wait_s", 1.0)),
            jitter_s=float(raw.get("jitter_s", 0.0)),
            region=tuple(raw.get("region", (0, 0, 100, 100))),  # type: ignore[arg-type]
            detection=raw.get("detection", DETECT_TEMPLATE),
            template_png=base64.b64decode(tpl) if tpl else None,
            match_threshold=float(raw.get("match_threshold", 0.8)),
            hsv_lower=tuple(raw.get("hsv_lower", (0, 100, 100))),  # type: ignore[arg-type]
            hsv_upper=tuple(raw.get("hsv_upper", (10, 255, 255))),  # type: ignore[arg-type]
            condition=raw.get("condition", COND_ABSENT),
            ratio_threshold=float(raw.get("ratio_threshold", 0.2)),
            timeout_s=float(raw.get("timeout_s", 30.0)),
            on_timeout=raw.get("on_timeout", TIMEOUT_STOP),
        )


@dataclass
class Routine:
    name: str = "Routine"
    steps: List[RoutineStep] = field(default_factory=list)
    loop_count: int = 1  # 0 = repeat forever

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": FILE_FORMAT,
            "version": FILE_VERSION,
            "name": self.name,
            "loop_count": self.loop_count,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Routine":
        return cls(
            name=raw.get("name", "Routine"),
            loop_count=int(raw.get("loop_count", 1)),
            steps=[RoutineStep.from_dict(s) for s in raw.get("steps", [])],
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Routine":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw)
