"""Records keyboard and mouse input into a :class:`Macro` using pynput.

Mouse-move events are throttled (and can be disabled entirely) so that
keyboard-only macros stay clean instead of being flooded with thousands of
motion samples. The app's global hotkeys (F9/F10/Esc) are excluded from the
recording so replaying a macro can never re-trigger record/play/panic.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable, List, Optional

from pynput import keyboard, mouse

from ..models.event import (
    KEY_DOWN,
    KEY_UP,
    MOUSE_CLICK,
    MOUSE_MOVE,
    MOUSE_SCROLL,
    Event,
)
from ..models.macro import Macro, trim_edge_clicks
from .hotkeys import DEFAULT_HOTKEY_EVENT_NAMES
from .keys import button_to_name, key_to_name

# Minimum seconds between recorded mouse-move samples.
MOVE_MIN_INTERVAL = 0.015


class Recorder:
    def __init__(
        self,
        record_mouse_move: bool = True,
        on_event: Optional[Callable[[Event], None]] = None,
        ignored_keys: Iterable[str] = DEFAULT_HOTKEY_EVENT_NAMES,
    ) -> None:
        self.record_mouse_move = record_mouse_move
        self._on_event = on_event
        self._ignored_keys = frozenset(ignored_keys)
        self.events: List[Event] = []
        self._kb: Optional[keyboard.Listener] = None
        self._mouse: Optional[mouse.Listener] = None
        self._last_time: float = 0.0
        self._last_move_time: float = 0.0
        self._running = False

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self.events = []
        self._last_time = time.perf_counter()
        self._last_move_time = 0.0
        self._running = True
        self._kb = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._mouse = mouse.Listener(
            on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll
        )
        self._kb.start()
        self._mouse.start()

    def stop(
        self, trim_leading_click: bool = False, trim_trailing_click: bool = False
    ) -> Macro:
        """Stop listening and return the recording.

        Pass ``trim_leading_click`` when recording was *started* from the GUI
        button and ``trim_trailing_click`` when it was *stopped* from it — the
        corresponding edge click (on the app's own window) is stripped so
        replays don't click on MacroEngine itself.
        """
        self._running = False
        if self._kb is not None:
            self._kb.stop()
            self._kb = None
        if self._mouse is not None:
            self._mouse.stop()
            self._mouse = None
        events = list(self.events)
        if trim_leading_click or trim_trailing_click:
            events = trim_edge_clicks(
                events, leading=trim_leading_click, trailing=trim_trailing_click
            )
        return Macro(name="Recorded", events=events, loop_count=1)

    @property
    def running(self) -> bool:
        return self._running

    # -- internals ----------------------------------------------------------
    def _append(self, type_: str, data: dict) -> None:
        # TODO(audit): _last_time/events are mutated from two listener threads
        # (keyboard + mouse) without a lock, so concurrent events can skew each
        # other's delay. Wrap timestamp+append in a threading.Lock.
        now = time.perf_counter()
        delay = now - self._last_time
        self._last_time = now
        ev = Event(type=type_, delay=delay, data=data)
        self.events.append(ev)
        if self._on_event is not None:
            self._on_event(ev)

    # keyboard
    def _on_press(self, key) -> None:
        name = key_to_name(key)
        if name in self._ignored_keys:
            return
        self._append(KEY_DOWN, {"key": name})

    def _on_release(self, key) -> None:
        name = key_to_name(key)
        if name in self._ignored_keys:
            return
        self._append(KEY_UP, {"key": name})

    # mouse
    def _on_move(self, x, y) -> None:
        if not self.record_mouse_move:
            return
        now = time.perf_counter()
        if now - self._last_move_time < MOVE_MIN_INTERVAL:
            return
        self._last_move_time = now
        self._append(MOUSE_MOVE, {"x": int(x), "y": int(y)})

    def _on_click(self, x, y, button, pressed) -> None:
        self._append(
            MOUSE_CLICK,
            {
                "x": int(x),
                "y": int(y),
                "button": button_to_name(button),
                "pressed": bool(pressed),
            },
        )

    def _on_scroll(self, x, y, dx, dy) -> None:
        self._append(
            MOUSE_SCROLL,
            {"x": int(x), "y": int(y), "dx": int(dx), "dy": int(dy)},
        )
