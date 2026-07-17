"""Replays a :class:`Macro` on a background thread, honoring per-event timing
and loop configuration. Playback is interruptible so the GUI's panic hotkey can
stop an infinite loop instantly.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from pynput import keyboard, mouse

from ..models.event import (
    KEY_DOWN,
    KEY_UP,
    MOUSE_CLICK,
    MOUSE_MOVE,
    MOUSE_SCROLL,
)
from ..models.macro import Macro
from .keys import name_to_button, name_to_key

# Sleep is chunked so stop() is honored quickly even across long delays.
_SLEEP_CHUNK = 0.02
# Guard against absurd recorded gaps making playback appear to hang.
_MAX_DELAY = 30.0


class Player:
    def __init__(
        self,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_progress = on_progress
        self._on_finished = on_finished
        self._kbd = keyboard.Controller()
        self._mouse = mouse.Controller()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._held_keys: set = set()
        self._held_buttons: set = set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def play(self, macro: Macro) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(macro,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    # -- worker -------------------------------------------------------------
    def _run(self, macro: Macro) -> None:
        # Track injected-but-not-yet-released inputs so a mid-macro stop (panic
        # hotkey) can't leave a key or mouse button held down forever.
        self._held_keys: set = set()
        self._held_buttons: set = set()
        try:
            loop = 0
            while not self._stop.is_set():
                for index, event in enumerate(macro.events):
                    if self._stop.is_set():
                        break
                    self._sleep(min(event.delay, _MAX_DELAY))
                    if self._stop.is_set():
                        break
                    self._perform(event)
                    if self._on_progress is not None:
                        self._on_progress(index, loop)
                loop += 1
                if macro.loop_count != 0 and loop >= macro.loop_count:
                    break
        finally:
            self._release_held()
            if self._on_finished is not None:
                self._on_finished()

    def _release_held(self) -> None:
        for key in list(self._held_keys):
            try:
                self._kbd.release(key)
            except Exception:
                pass
        self._held_keys.clear()
        for button in list(self._held_buttons):
            try:
                self._mouse.release(button)
            except Exception:
                pass
        self._held_buttons.clear()

    def _sleep(self, seconds: float) -> None:
        end = time.perf_counter() + seconds
        while not self._stop.is_set():
            remaining = end - time.perf_counter()
            if remaining <= 0:
                return
            time.sleep(min(_SLEEP_CHUNK, remaining))

    def _perform(self, event) -> None:
        d = event.data
        if event.type == KEY_DOWN:
            key = name_to_key(d["key"])
            self._kbd.press(key)
            self._held_keys.add(key)
        elif event.type == KEY_UP:
            key = name_to_key(d["key"])
            self._kbd.release(key)
            self._held_keys.discard(key)
        elif event.type == MOUSE_MOVE:
            self._mouse.position = (d["x"], d["y"])
        elif event.type == MOUSE_CLICK:
            self._mouse.position = (d["x"], d["y"])
            button = name_to_button(d["button"])
            if d.get("pressed"):
                self._mouse.press(button)
                self._held_buttons.add(button)
            else:
                self._mouse.release(button)
                self._held_buttons.discard(button)
        elif event.type == MOUSE_SCROLL:
            self._mouse.position = (d["x"], d["y"])
            self._mouse.scroll(d.get("dx", 0), d.get("dy", 0))
