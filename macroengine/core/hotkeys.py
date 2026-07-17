"""Global hotkeys so recording/playback can be driven while a game has focus.

Wraps :class:`pynput.keyboard.GlobalHotKeys`. Callbacks fire on pynput's own
listener thread; when driving a Qt GUI, hand in callbacks that emit a Qt signal
so the work is marshaled back to the UI thread.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from pynput import keyboard

# Defaults (pynput hotkey syntax). The panic key stops everything immediately.
DEFAULT_RECORD = "<f9>"
DEFAULT_PLAY = "<f10>"
DEFAULT_PANIC = "<esc>"


class HotkeyManager:
    def __init__(
        self,
        on_record: Callable[[], None],
        on_play: Callable[[], None],
        on_panic: Callable[[], None],
        record_key: str = DEFAULT_RECORD,
        play_key: str = DEFAULT_PLAY,
        panic_key: str = DEFAULT_PANIC,
    ) -> None:
        self._mapping: Dict[str, Callable[[], None]] = {
            record_key: on_record,
            play_key: on_play,
            panic_key: on_panic,
        }
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def start(self) -> None:
        if self._listener is not None:
            return
        self._listener = keyboard.GlobalHotKeys(self._mapping)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
