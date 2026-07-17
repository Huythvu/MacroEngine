"""Save/load the app's automation config in one JSON file: vision triggers, buff
groups, and auto inputs. Backward compatible with older files that lack the newer
sections.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

from .autoinput import AutoInput
from .buff import BuffGroup
from .trigger import Trigger

FILE_FORMAT = "macroengine.watchers"
FILE_VERSION = 3


def save_watchers(
    triggers: List[Trigger],
    groups: List[BuffGroup],
    path: str | Path,
    auto_inputs: Optional[List[AutoInput]] = None,
) -> None:
    payload = {
        "format": FILE_FORMAT,
        "version": FILE_VERSION,
        "triggers": [t.to_dict() for t in triggers],
        "buff_groups": [g.to_dict() for g in groups],
        "auto_inputs": [a.to_dict() for a in (auto_inputs or [])],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_watchers(
    path: str | Path,
) -> Tuple[List[Trigger], List[BuffGroup], List[AutoInput]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    triggers = [Trigger.from_dict(t) for t in raw.get("triggers", [])]
    groups = [BuffGroup.from_dict(g) for g in raw.get("buff_groups", [])]
    autos = [AutoInput.from_dict(a) for a in raw.get("auto_inputs", [])]
    return triggers, groups, autos
