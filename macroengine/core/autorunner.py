"""Runs auto inputs: each enabled :class:`AutoInput` fires on its own timer.

A single background thread tracks the next-due time per action and performs it when
due, then reschedules using ``interval_s`` (± ``jitter_s``). Interruptible so the
GUI panic hotkey stops it immediately.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from pynput import keyboard, mouse

from ..models.autoinput import (
    AUTO_CLICK,
    AUTO_PRESS_KEY,
    AUTO_RUN_MACRO,
    AUTO_TYPE_TEXT,
    AutoInput,
)
from ..models.macro import Macro
from . import keyspec
from .keys import name_to_button
from .player import Player

# Scheduler granularity. Intervals shorter than this can't be timed precisely.
TICK = 0.005


class AutoRunner:
    def __init__(
        self,
        actions: List[AutoInput],
        on_fire: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._actions = actions
        self._on_fire = on_fire
        self._kbd = keyboard.Controller()
        self._mouse = mouse.Controller()
        self._player = Player()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._player.stop()

    # -- worker -------------------------------------------------------------
    def _run(self) -> None:
        # Fire each action as soon as it becomes due; first fire is one interval in.
        due: dict[int, float] = {}
        now = time.perf_counter()
        for ai in self._actions:
            due[id(ai)] = now + ai.next_interval()
        while not self._stop.is_set():
            now = time.perf_counter()
            for ai in list(self._actions):
                if not ai.enabled:
                    continue
                when = due.get(id(ai))
                if when is None:
                    due[id(ai)] = now + ai.next_interval()
                    continue
                if now >= when:
                    self._fire(ai)
                    due[id(ai)] = now + ai.next_interval()
            # TODO(audit): this ticks every 5 ms even when the nearest due time
            # is seconds away; sleeping min(due) - now (capped at TICK floor)
            # would cut idle CPU. Also: `due` is keyed by id(obj) — same caveat
            # as Monitor._cooldown_ok (id reuse / reset on edit).
            time.sleep(TICK)

    def _fire(self, ai: AutoInput) -> None:
        if ai.action == AUTO_PRESS_KEY:
            keyspec.press_keystroke(self._kbd, ai.key)
        elif ai.action == AUTO_TYPE_TEXT:
            keyspec.type_text(self._kbd, ai.text)
        elif ai.action == AUTO_CLICK:
            self._mouse.position = (ai.x, ai.y)
            button = name_to_button(ai.button)
            self._mouse.press(button)
            self._mouse.release(button)
        elif ai.action == AUTO_RUN_MACRO:
            if ai.macro_path and not self._player.running:
                try:
                    self._player.play(Macro.load(ai.macro_path))
                except Exception:
                    pass
        if self._on_fire is not None:
            self._on_fire(ai.name)
