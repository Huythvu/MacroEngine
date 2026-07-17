"""Background loop that watches regions and fires actions.

Two kinds of watcher are evaluated each tick:
  * plain triggers — one region + one condition (template or color),
  * buff groups — one shared region searched for several buff icons at once.

For each, when the condition holds and the item's cooldown has elapsed, the action
runs (tap a key, or play a saved macro).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from pynput import keyboard, mouse

from ..core import keyspec
from ..core.player import Player
from ..models.buff import BuffGroup
from ..models.macro import Macro
from ..models.trigger import (
    ACTION_CLICK_MATCH,
    ACTION_PRESS_KEY,
    ACTION_RUN_MACRO,
    Trigger,
)
from . import capture, detector

DEFAULT_POLL_INTERVAL = 0.15


class Monitor:
    def __init__(
        self,
        triggers: List[Trigger],
        groups: Optional[List[BuffGroup]] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        on_fire: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._triggers = triggers
        self._groups = groups if groups is not None else []
        self._poll_interval = poll_interval
        self._on_fire = on_fire
        self._kbd = keyboard.Controller()
        self._mouse = mouse.Controller()
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
                # TODO(audit): swallowing every exception hides real problems
                # (bad region, capture failure). Route through the logging
                # module (the app currently has no logging at all).
                except Exception:  # a bad region/template must not kill the loop
                    continue
            for group in list(self._groups):
                if self._stop.is_set():
                    break
                if not group.enabled:
                    continue
                try:
                    self._evaluate_group(group)
                except Exception:
                    continue
            # Pace the loop.
            elapsed = time.perf_counter() - tick
            if elapsed < self._poll_interval:
                time.sleep(self._poll_interval - elapsed)

    def _evaluate(self, trig: Trigger) -> None:
        image = capture.grab_region(trig.region)
        if not detector.condition_met(trig, image):
            return
        # For click-on-match, locate the reference in the already-captured frame
        # so we click exactly what the condition just saw.
        click_pos = None
        if trig.action == ACTION_CLICK_MATCH:
            if not trig.template_png:
                return
            score, box = detector.template_locate(
                image, detector.decode_png(trig.template_png)
            )
            if score < trig.match_threshold:
                return  # condition fired but there is nothing on screen to click
            click_pos = detector.match_screen_center(trig.region, box)
        if self._cooldown_ok(id(trig), trig.cooldown_s):
            self._do_action(
                trig.action, trig.action_key, trig.action_macro_path, trig.name,
                click_pos=click_pos,
            )

    def _evaluate_group(self, group: BuffGroup) -> None:
        # Capture the shared bar region once, then test every buff icon against it.
        image = capture.grab_region(group.region)
        for item in group.items:
            if not item.enabled:
                continue
            met, _score, _present = detector.buff_item_met(item, image)
            if not met:
                continue
            if self._cooldown_ok(id(item), item.cooldown_s):
                label = f"{group.name}/{item.name}"
                self._do_action(item.action, item.action_key, item.action_macro_path, label)

    # TODO(audit): _last_fire is keyed by id(obj); CPython can reuse ids after
    # GC and replacing an item on edit silently resets its cooldown. Use a
    # stable per-object token (e.g. a uuid field) if this ever matters.
    def _cooldown_ok(self, key: int, cooldown_s: float) -> bool:
        now = time.perf_counter()
        if now - self._last_fire.get(key, 0.0) < cooldown_s:
            return False
        self._last_fire[key] = now
        return True

    def _do_action(
        self, action: str, key: str, macro_path: str, label: str, click_pos=None
    ) -> None:
        if action == ACTION_PRESS_KEY:
            keyspec.press_keystroke(self._kbd, key)
        elif action == ACTION_CLICK_MATCH:
            if click_pos is None:
                return
            self._mouse.position = click_pos
            self._mouse.press(mouse.Button.left)
            self._mouse.release(mouse.Button.left)
        elif action == ACTION_RUN_MACRO:
            if macro_path and not self._player.running:
                try:
                    self._player.play(Macro.load(macro_path))
                except Exception:
                    # TODO(audit): a missing/corrupt macro file fails silently
                    # every tick — log it and surface once in the status bar.
                    pass
        if self._on_fire is not None:
            self._on_fire(label)
