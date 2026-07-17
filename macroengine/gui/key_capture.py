"""A widget for entering a keystroke spec (see core.keyspec).

The field is editable (type ``ctrl+shift+a`` directly), and the **Capture** button
lets you just *press* the key/combo you want — including lone modifiers (Alt),
special keys (Esc/Backspace) and combos (Ctrl+C).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

# Qt key -> spec token for the non-character special keys.
_SPECIAL = {
    Qt.Key_Escape: "esc",
    Qt.Key_Tab: "tab",
    Qt.Key_Backtab: "tab",
    Qt.Key_Backspace: "backspace",
    Qt.Key_Return: "enter",
    Qt.Key_Enter: "enter",
    Qt.Key_Insert: "insert",
    Qt.Key_Delete: "delete",
    Qt.Key_Home: "home",
    Qt.Key_End: "end",
    Qt.Key_PageUp: "page_up",
    Qt.Key_PageDown: "page_down",
    Qt.Key_Left: "left",
    Qt.Key_Right: "right",
    Qt.Key_Up: "up",
    Qt.Key_Down: "down",
    Qt.Key_Space: "space",
    Qt.Key_CapsLock: "caps_lock",
    Qt.Key_NumLock: "num_lock",
    Qt.Key_ScrollLock: "scroll_lock",
    Qt.Key_Print: "print_screen",
    Qt.Key_Pause: "pause",
    Qt.Key_Menu: "menu",
}

_MODIFIER_KEYS = {
    Qt.Key_Control: "ctrl",
    Qt.Key_Alt: "alt",
    Qt.Key_AltGr: "alt_gr",
    Qt.Key_Shift: "shift",
    Qt.Key_Meta: "cmd",
}


def _main_token(key: int, text: str) -> Optional[str]:
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key).lower()
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    if Qt.Key_F1 <= key <= Qt.Key_F35:
        return f"f{key - Qt.Key_F1 + 1}"
    if key in _SPECIAL:
        return _SPECIAL[key]
    if text and text.isprintable() and len(text) == 1 and not text.isspace():
        return text.lower()
    return None


def _modifier_tokens(modifiers) -> list:
    out = []
    if modifiers & Qt.ControlModifier:
        out.append("ctrl")
    if modifiers & Qt.AltModifier:
        out.append("alt")
    if modifiers & Qt.ShiftModifier:
        out.append("shift")
    if modifiers & Qt.MetaModifier:
        out.append("cmd")
    return out


class _CaptureLineEdit(QLineEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._capturing = False
        self._saw_main = False

    def start_capture(self) -> None:
        self._capturing = True
        self._saw_main = False
        self.clear()
        self.setPlaceholderText("press a key or combo…")
        self.setFocus()

    def _finish(self, spec: str) -> None:
        self._capturing = False
        self.setPlaceholderText("")
        self.setText(spec)

    def keyPressEvent(self, event) -> None:
        if not self._capturing:
            return super().keyPressEvent(event)
        key = event.key()
        if key in _MODIFIER_KEYS:
            # A bare modifier so far — wait to see if a main key follows.
            event.accept()
            return
        token = _main_token(key, event.text())
        if token is None:
            event.accept()
            return
        self._saw_main = True
        spec = "+".join(_modifier_tokens(event.modifiers()) + [token])
        self._finish(spec)
        event.accept()

    def keyReleaseEvent(self, event) -> None:
        if not self._capturing:
            return super().keyReleaseEvent(event)
        key = event.key()
        # Releasing a modifier with no main key pressed = a lone modifier (e.g. Alt).
        if key in _MODIFIER_KEYS and not self._saw_main:
            self._finish(_MODIFIER_KEYS[key])
        event.accept()


class KeyCaptureEdit(QWidget):
    def __init__(self, keystroke: str = "", parent=None) -> None:
        super().__init__(parent)
        self._edit = _CaptureLineEdit()
        self._edit.setText(keystroke)
        self._edit.setPlaceholderText("e.g. a, esc, ctrl+c")
        btn = QPushButton("Capture")
        btn.setToolTip("Click, then press the key or combo you want to send")
        btn.clicked.connect(self._edit.start_capture)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._edit, 1)
        row.addWidget(btn)

    def keystroke(self) -> str:
        return self._edit.text().strip()

    def set_keystroke(self, spec: str) -> None:
        self._edit.setText(spec)
