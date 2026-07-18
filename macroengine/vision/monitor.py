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
from ..models import actions
from ..models.buff import BuffGroup
from ..models.macro import Macro
from ..models.trigger import Trigger
from . import capture, detector

DEFAULT_POLL_INTERVAL = 0.15

# Sentinel: a click-on-match action whose reference is not on screen right now.
_NO_CLICK = object()


class Monitor:
    def __init__(
        self,
        triggers: List[Trigger],
        groups: Optional[List[BuffGroup]] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        on_fire: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._triggers = triggers
        self._groups = groups if groups is not None else []
        self._poll_interval = poll_interval
        self._on_fire = on_fire
        self._on_log = on_log
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

    def _log(self, message: str) -> None:
        import logging

        logging.getLogger("macroengine.monitor").warning(message)
        if self._on_log is not None:
            self._on_log(message)

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
                except Exception as exc:  # a bad region/template must not kill the loop
                    self._log(f"trigger '{trig.name}' error: {exc}")
            for group in list(self._groups):
                if self._stop.is_set():
                    break
                if not group.enabled:
                    continue
                try:
                    self._evaluate_group(group)
                except Exception as exc:
                    self._log(f"buff group '{group.name}' error: {exc}")
            # Pace the loop.
            elapsed = time.perf_counter() - tick
            if elapsed < self._poll_interval:
                time.sleep(self._poll_interval - elapsed)

    def _evaluate(self, trig: Trigger) -> None:
        image = capture.grab_region(trig.region)
        if not detector.condition_met(trig, image):
            return
        click_pos = self._locate_for_click(trig, image, trig.region)
        if click_pos is _NO_CLICK:
            return  # click_match requested but nothing on screen to click
        if self._cooldown_ok(id(trig), trig.cooldown_s):
            self._do_action(trig, trig.name, click_pos=click_pos)

    def _evaluate_group(self, group: BuffGroup) -> None:
        # Capture the shared bar region once, then test every buff icon against it.
        image = capture.grab_region(group.region)
        for item in group.items:
            if not item.enabled:
                continue
            met, _score, _present = detector.buff_item_met(item, image)
            if not met:
                continue
            click_pos = self._locate_for_click(item, image, group.region)
            if click_pos is _NO_CLICK:
                continue
            if self._cooldown_ok(id(item), item.cooldown_s):
                self._do_action(item, f"{group.name}/{item.name}", click_pos=click_pos)

    def _locate_for_click(self, obj, image, region):
        """For click-on-match actions, locate the reference in the frame the
        condition just evaluated so we click exactly what it saw.

        Returns the screen position, ``None`` (no click needed), or the
        ``_NO_CLICK`` sentinel when a click was requested but the reference
        is not actually on screen.
        """
        if obj.action != actions.CLICK_MATCH:
            return None
        if not obj.template_png:
            return _NO_CLICK
        score, box = detector.template_locate(
            image, detector.decode_png(obj.template_png)
        )
        if score < obj.match_threshold:
            return _NO_CLICK
        return detector.match_screen_center(region, box)

    # TODO(audit): _last_fire is keyed by id(obj); CPython can reuse ids after
    # GC and replacing an item on edit silently resets its cooldown. Use a
    # stable per-object token (e.g. a uuid field) if this ever matters.
    def _cooldown_ok(self, key: int, cooldown_s: float) -> bool:
        now = time.perf_counter()
        if now - self._last_fire.get(key, 0.0) < cooldown_s:
            return False
        self._last_fire[key] = now
        return True

    def _do_action(self, obj, label: str, click_pos=None) -> None:
        """Perform ``obj``'s action (shared vocabulary — Trigger or BuffItem)."""
        action = obj.action
        if action == actions.PRESS_KEY:
            keyspec.press_keystroke(self._kbd, obj.action_key)
        elif action == actions.TYPE_TEXT:
            keyspec.type_text(self._kbd, obj.action_text)
        elif action == actions.CLICK_AT:
            self._click((obj.action_x, obj.action_y), obj.action_button)
        elif action == actions.CLICK_MATCH:
            if click_pos is None:
                return
            self._click(click_pos, "left")
        elif action == actions.RUN_MACRO:
            if obj.action_macro_path and not self._player.running:
                try:
                    self._player.play(Macro.load(obj.action_macro_path))
                except Exception:
                    # TODO(audit): a missing/corrupt macro file fails silently
                    # every tick — log it and surface once in the status bar.
                    pass
        if self._on_fire is not None:
            self._on_fire(label)

    def _click(self, pos, button_name: str) -> None:
        self._mouse.position = pos
        button = getattr(mouse.Button, button_name, mouse.Button.left)
        self._mouse.press(button)
        self._mouse.release(button)
