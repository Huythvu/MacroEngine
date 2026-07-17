"""Background loop that watches trigger regions and fires their actions.

Each tick it captures every enabled trigger's region, evaluates the condition
(:func:`detector.condition_met`), and — if met and the trigger's cooldown has
elapsed — performs the action (tap a key, or play a saved macro).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from pynput import keyboard

from ..core.keys import name_to_key
from ..core.player import Player
from ..models.macro import Macro
from ..models.trigger import ACTION_PRESS_KEY, ACTION_RUN_MACRO, Trigger
from . import capture, detector

DEFAULT_POLL_INTERVAL = 0.15


class Monitor:
    def __init__(
        self,
        triggers: List[Trigger],
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        on_fire: Optional[Callable[[Trigger], None]] = None,
    ) -> None:
        self._triggers = triggers
        self._poll_interval = poll_interval
        self._on_fire = on_fire
        self._kbd = keyboard.Controller()
        self._player = Player()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_fire: dict[int, float] = {}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._last_fire.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._player.stop()

    # -- worker -------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            tick = time.perf_counter()
            for trig in list(self._triggers):
                if self._stop.is_set():
                    break
                if not trig.enabled:
                    continue
                try:
                    self._evaluate(trig)
                except Exception:  # a bad region/template must not kill the loop
                    continue
            # Pace the loop.
            elapsed = time.perf_counter() - tick
            if elapsed < self._poll_interval:
                time.sleep(self._poll_interval - elapsed)

    def _evaluate(self, trig: Trigger) -> None:
        image = capture.grab_region(trig.region)
        if not detector.condition_met(trig, image):
            return
        now = time.perf_counter()
        last = self._last_fire.get(id(trig), 0.0)
        if now - last < trig.cooldown_s:
            return
        self._last_fire[id(trig)] = now
        self._fire(trig)

    def _fire(self, trig: Trigger) -> None:
        if trig.action == ACTION_PRESS_KEY:
            key = name_to_key(trig.action_key)
            self._kbd.press(key)
            self._kbd.release(key)
        elif trig.action == ACTION_RUN_MACRO:
            if trig.action_macro_path and not self._player.running:
                try:
                    self._player.play(Macro.load(trig.action_macro_path))
                except Exception:
                    pass
        if self._on_fire is not None:
            self._on_fire(trig)
