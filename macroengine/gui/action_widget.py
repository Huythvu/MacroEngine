"""The shared action editor.

One widget for "what should happen": press key/combo, type text, click at a
picked position, click on the found image, or run a macro (picked from the
library or browsed). Used by the trigger, buff-item, and auto-input dialogs so
every feature offers the same actions with the same UI.
"""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ..models import actions
from ..models.macro import Macro
from ..paths import macros_dir
from .key_capture import KeyCaptureEdit
from .region_selector import PointPicker
from .util import wrap


class ActionWidget(QWidget):
    """Edits an action + its parameters.

    ``allowed`` restricts which actions this context offers (e.g. auto inputs
    have no template, so no click-on-match). Values are read/written via plain
    keyword access so callers map them onto their own model fields.
    """

    def __init__(
        self,
        allowed: Iterable[str],
        action: str = actions.PRESS_KEY,
        key: str = "1",
        text: str = "",
        x: int = 0,
        y: int = 0,
        button: str = "left",
        macro_path: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._x, self._y, self._button = int(x), int(y), button or "left"

        self._action = QComboBox()
        for act in allowed:
            self._action.addItem(actions.LABELS.get(act, act), act)
        idx = self._action.findData(action)
        self._action.setCurrentIndex(max(0, idx))
        self._action.currentIndexChanged.connect(self._sync)

        # press key / combo
        self._key = KeyCaptureEdit(key)

        # type text
        self._text = QLineEdit(text)
        self._text.setPlaceholderText("text to type, e.g. 123asd")

        # click at position
        self._pos_label = QLabel(self._pos_text())
        btn_pick = QPushButton("Pick on screen…")
        btn_pick.clicked.connect(self._pick)
        pos_row = QHBoxLayout()
        pos_row.addWidget(self._pos_label, 1)
        pos_row.addWidget(btn_pick)
        self._pos_widget = wrap(pos_row)

        # click on found image — no parameters, just an explainer
        self._match_note = QLabel(
            "Left-clicks the center of wherever the reference image is found."
        )
        self._match_note.setWordWrap(True)

        # run macro — pick from library, or browse
        self._macro_combo = QComboBox()
        self._macro_combo.addItem("— pick from library —", "")
        for p in sorted(macros_dir().glob("*.json")):
            try:
                name = Macro.load(p).name or p.stem
            except Exception:  # noqa: BLE001
                name = p.stem
            self._macro_combo.addItem(name, str(p))
        self._macro_combo.currentIndexChanged.connect(self._pick_macro)
        self._macro_path = QLineEdit(macro_path)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        macro_row = QHBoxLayout()
        macro_row.addWidget(self._macro_path, 1)
        macro_row.addWidget(btn_browse)
        self._macro_widget = wrap(macro_row)

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Action:", self._action)
        self._key_label = QLabel("Key:")
        form.addRow(self._key_label, self._key)
        self._text_label = QLabel("Text:")
        form.addRow(self._text_label, self._text)
        self._pos_label_row = QLabel("Position:")
        form.addRow(self._pos_label_row, self._pos_widget)
        self._match_label_row = QLabel("")
        form.addRow(self._match_label_row, self._match_note)
        self._macro_lib_label = QLabel("From library:")
        form.addRow(self._macro_lib_label, self._macro_combo)
        self._macro_label = QLabel("Macro:")
        form.addRow(self._macro_label, self._macro_widget)
        self._sync()

    # -- public --------------------------------------------------------------
    @property
    def action(self) -> str:
        return self._action.currentData()

    def values(self) -> dict:
        """Current action + parameters, ready to map onto model fields."""
        return {
            "action": self._action.currentData(),
            "key": self._key.keystroke() or "1",
            "text": self._text.text(),
            "x": self._x,
            "y": self._y,
            "button": self._button,
            "macro_path": self._macro_path.text().strip(),
        }

    # -- internals -----------------------------------------------------------
    def _pos_text(self) -> str:
        return f"{self._button}-click at ({self._x}, {self._y})"

    def _pick(self) -> None:
        picker = PointPicker(self)
        if picker.exec() and picker.point is not None:
            self._x, self._y = picker.point
            self._button = picker.button
            self._pos_label.setText(self._pos_text())

    def _pick_macro(self, _index: int) -> None:
        path = self._macro_combo.currentData()
        if path:
            self._macro_path.setText(path)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select macro", str(macros_dir()), "Macro files (*.json);;All files (*)"
        )
        if path:
            self._macro_path.setText(path)

    def _sync(self) -> None:
        act = self._action.currentData()
        vis = {
            actions.PRESS_KEY: (self._key_label, self._key),
            actions.TYPE_TEXT: (self._text_label, self._text),
            actions.CLICK_AT: (self._pos_label_row, self._pos_widget),
            actions.CLICK_MATCH: (self._match_label_row, self._match_note),
            actions.RUN_MACRO: (
                self._macro_lib_label, self._macro_combo,
                self._macro_label, self._macro_widget,
            ),
        }
        for action, widgets in vis.items():
            for w in widgets:
                w.setVisible(action == act)
