"""Save/load the full set of vision watchers — plain triggers *and* buff groups —
in a single JSON file. Backward compatible with old trigger-only files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

from .buff import BuffGroup
from .trigger import Trigger

FILE_FORMAT = "macroengine.watchers"
FILE_VERSION = 2


def save_watchers(triggers: List[Trigger], groups: List[BuffGroup], path: str | Path) -> None:
    payload = {
        "format": FILE_FORMAT,
        "version": FILE_VERSION,
        "triggers": [t.to_dict() for t in triggers],
        "buff_groups": [g.to_dict() for g in groups],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_watchers(path: str | Path) -> Tuple[List[Trigger], List[BuffGroup]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    triggers = [Trigger.from_dict(t) for t in raw.get("triggers", [])]
    groups = [BuffGroup.from_dict(g) for g in raw.get("buff_groups", [])]
    return triggers, groups
