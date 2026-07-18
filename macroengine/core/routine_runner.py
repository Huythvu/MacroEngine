"""Executes a :class:`Routine` on a background thread.

Steps run in order (skipping disabled ones); the whole routine repeats
``loop_count`` times (0 = forever). Interruptible at every point — the panic
hotkey stops mid-macro (releasing held keys via Player), mid-wait, and mid-poll.
"""

from __future__ import annotations

import random
import threading
import time
from typing import Callable, Optional

from pynput import keyboard, mouse

from ..models import actions
from ..models.macro import Macro
from ..models.routine import (
    STEP_IF_VISION,
    STEP_MACRO,
    STEP_WAIT,
    STEP_WAIT_VISION,
    TIMEOUT_STOP,
    Routine,
    RoutineStep,
)
from ..vision import capture, detector
from . import keyspec
from .keys import name_to_button
from .player import Player

_SLEEP_CHUNK = 0.05
VISION_POLL_INTERVAL = 0.2


class RoutineRunner:
    def __init__(
        self,
        on_step: Optional[Callable[[int, str], None]] = None,
        on_finished: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._on_step = on_step
        self._on_finished = on_finished
        self._player = Player()
        self._mouse = mouse.Controller()
        self._kbd = keyboard.Controller()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def run(self, routine: Routine) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(routine,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._player.stop()

    # -- worker -------------------------------------------------------------
    def _run(self, routine: Routine) -> None:
        reason = "Routine finished"
        try:
            loop = 0
            while not self._stop.is_set():
                for index, step in enumerate(routine.steps):
                    if self._stop.is_set():
                        reason = "Stopped"
                        return
                    if not step.enabled:
                        continue
                    self._notify_step(index, step)
                    ok, why = self._run_step(step)
                    if not ok:
                        reason = f"Stopped at step {index + 1} ({step.label()}): {why}"
                        return
                loop += 1
                if routine.loop_count != 0 and loop >= routine.loop_count:
                    return
        finally:
            if self._stop.is_set() and reason == "Routine finished":
                reason = "Stopped"
            if self._on_finished is not None:
                self._on_finished(reason)

    def _notify_step(self, index: int, step: RoutineStep) -> None:
        if self._on_step is not None:
            self._on_step(index, step.label())

    def _run_step(self, step: RoutineStep) -> tuple:
        """Returns ``(ok, why)`` — ``ok=False`` aborts the routine."""
        if step.type == STEP_MACRO:
            return self._run_macro(step)
        if step.type == STEP_WAIT:
            self._sleep(max(0.0, step.wait_s + random.uniform(-step.jitter_s, step.jitter_s))
                        if step.jitter_s > 0 else step.wait_s)
            return (True, "")
        if step.type == STEP_WAIT_VISION:
            return self._wait_vision(step)
        if step.type == STEP_IF_VISION:
            return self._if_vision(step)
        return (True, "")  # unknown step types are ignored

    def _run_macro(self, step: RoutineStep) -> tuple:
        try:
            if step.inline_macro is not None:
                macro = Macro.from_dict(step.inline_macro)
            else:
                macro = Macro.load(step.macro_path)
        except Exception as exc:  # noqa: BLE001
            src = "recorded macro" if step.inline_macro is not None else f"'{step.macro_path}'"
            return (False, f"could not load {src}: {exc}")
        if step.loop_override > 0:
            macro.loop_count = step.loop_override
        elif macro.loop_count == 0:
            # A macro saved as loop-forever would hang the routine; play it once
            # here — the routine's own loop_count handles repetition.
            macro.loop_count = 1
        self._player.play(macro)
        while self._player.running and not self._stop.is_set():
            time.sleep(_SLEEP_CHUNK)
        if self._stop.is_set():
            self._player.stop()
            self._player.join(timeout=2.0)
            return (False, "stopped")
        return (True, "")

    def _wait_vision(self, step: RoutineStep) -> tuple:
        trigger = step.to_trigger()
        deadline = (
            time.perf_counter() + step.timeout_s if step.timeout_s > 0 else None
        )
        while not self._stop.is_set():
            try:
                image = capture.grab_region(step.region)
                if detector.condition_met(trigger, image):
                    self._maybe_click_match(step, image)
                    return (True, "")
            except Exception as exc:  # noqa: BLE001
                return (False, f"capture failed: {exc}")
            if deadline is not None and time.perf_counter() >= deadline:
                if step.on_timeout == TIMEOUT_STOP:
                    return (False, f"timed out after {step.timeout_s:g}s")
                return (True, "")  # continue anyway (no click — nothing was found)
            self._sleep(VISION_POLL_INTERVAL)
        return (False, "stopped")

    def _if_vision(self, step: RoutineStep) -> tuple:
        """Check the condition once; run then/else action; continue."""
        try:
            image = capture.grab_region(step.region)
        except Exception as exc:  # noqa: BLE001
            return (False, f"capture failed: {exc}")
        met = detector.condition_met(step.to_trigger(), image)
        action = step.then_action if met else step.else_action
        self._run_action(action)
        return (True, "")

    def _run_action(self, action) -> None:
        """Execute an embedded Action (shared vocabulary)."""
        if action.kind == actions.PRESS_KEY:
            keyspec.press_keystroke(self._kbd, action.key)
        elif action.kind == actions.TYPE_TEXT:
            keyspec.type_text(self._kbd, action.text)
        elif action.kind == actions.CLICK_AT:
            self._mouse.position = (action.x, action.y)
            button = name_to_button(action.button)
            self._mouse.press(button)
            self._mouse.release(button)
        elif action.kind == actions.RUN_MACRO:
            if action.macro_path:
                try:
                    self._player.play(Macro.load(action.macro_path))
                    while self._player.running and not self._stop.is_set():
                        time.sleep(_SLEEP_CHUNK)
                except Exception:  # noqa: BLE001
                    pass
        # actions.NONE / CLICK_MATCH: nothing to do here

    def _maybe_click_match(self, step: RoutineStep, image) -> None:
        """After the condition is met, optionally click the found reference —
        located in the same frame the condition just evaluated."""
        if not step.click_on_match or not step.template_png:
            return
        score, box = detector.template_locate(
            image, detector.decode_png(step.template_png)
        )
        if score < step.match_threshold:
            return  # e.g. an 'absent' condition — nothing on screen to click
        self._mouse.position = detector.match_screen_center(step.region, box)
        self._mouse.press(mouse.Button.left)
        self._mouse.release(mouse.Button.left)

    def _sleep(self, seconds: float) -> None:
        end = time.perf_counter() + seconds
        while not self._stop.is_set():
            remaining = end - time.perf_counter()
            if remaining <= 0:
                return
            time.sleep(min(_SLEEP_CHUNK, remaining))
