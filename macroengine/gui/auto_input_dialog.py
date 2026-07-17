"""Dialog to create or edit a single :class:`AutoInput` (a timed repeater)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models.autoinput import (
    AUTO_CLICK,
    AUTO_PRESS_KEY,
    AUTO_RUN_MACRO,
    AutoInput,
)
from .region_selector import PointPicker


class AutoInputDialog(QDialog):
    def __init__(self, auto: Optional[AutoInput] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto Input")
        self._auto = auto or AutoInput()
        self._x, self._y, self._button = self._auto.x, self._auto.y, self._auto.button

        self._name = QLineEdit(self._auto.name)

        self._action = QComboBox()
        self._action.addItem("Press key", AUTO_PRESS_KEY)
        self._action.addItem("Click at position", AUTO_CLICK)
        self._action.addItem("Run macro", AUTO_RUN_MACRO)
        self._action.setCurrentIndex(
            {AUTO_PRESS_KEY: 0, AUTO_CLICK: 1, AUTO_RUN_MACRO: 2}.get(self._auto.action, 0)
        )
        self._action.currentIndexChanged.connect(self._sync)

        # press key
        self._key = QLineEdit(self._auto.key)

        # click
        self._pos_label = QLabel(self._pos_text())
        btn_pick = QPushButton("Pick on screen…")
        btn_pick.clicked.connect(self._pick)
        pos_row = QHBoxLayout()
        pos_row.addWidget(self._pos_label, 1)
        pos_row.addWidget(btn_pick)
        self._pos_widget = _wrap(pos_row)

        # run macro
        self._macro = QLineEdit(self._auto.macro_path)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        macro_row = QHBoxLayout()
        macro_row.addWidget(self._macro, 1)
        macro_row.addWidget(btn_browse)
        self._macro_widget = _wrap(macro_row)

        self._interval = QDoubleSpinBox()
        self._interval.setRange(0.01, 3600.0)
        self._interval.setDecimals(3)
        self._interval.setSingleStep(0.1)
        self._interval.setValue(self._auto.interval_s)

        self._jitter = QDoubleSpinBox()
        self._jitter.setRange(0.0, 60.0)
        self._jitter.setDecimals(3)
        self._jitter.setSingleStep(0.05)
        self._jitter.setValue(self._auto.jitter_s)
        self._jitter.setToolTip("Random +/- added to each interval (0 = exact timing)")

        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Action:", self._action)
        self._key_label = QLabel("Key:")
        form.addRow(self._key_label, self._key)
        self._pos_form_label = QLabel("Position:")
        form.addRow(self._pos_form_label, self._pos_widget)
        self._macro_form_label = QLabel("Macro:")
        form.addRow(self._macro_form_label, self._macro_widget)
        form.addRow("Interval (s):", self._interval)
        form.addRow("Jitter ± (s):", self._jitter)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)
        self._sync()

    def _pos_text(self) -> str:
        return f"{self._button}-click at ({self._x}, {self._y})"

    def _pick(self) -> None:
        picker = PointPicker(self)
        if picker.exec() and picker.point is not None:
            self._x, self._y = picker.point
            self._button = picker.button
            self._pos_label.setText(self._pos_text())

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select macro", "", "Macro files (*.json);;All files (*)"
        )
        if path:
            self._macro.setText(path)

    def _sync(self) -> None:
        action = self._action.currentData()
        is_key = action == AUTO_PRESS_KEY
        is_click = action == AUTO_CLICK
        is_macro = action == AUTO_RUN_MACRO
        self._key_label.setVisible(is_key)
        self._key.setVisible(is_key)
        self._pos_form_label.setVisible(is_click)
        self._pos_widget.setVisible(is_click)
        self._macro_form_label.setVisible(is_macro)
        self._macro_widget.setVisible(is_macro)

    def get_auto(self) -> AutoInput:
        a = self._auto
        a.name = self._name.text() or "Auto input"
        a.action = self._action.currentData()
        a.key = self._key.text() or "1"
        a.x, a.y, a.button = self._x, self._y, self._button
        a.macro_path = self._macro.text()
        a.interval_s = float(self._interval.value())
        a.jitter_s = float(self._jitter.value())
        return a


# TODO(audit): duplicated helper — see note in trigger_dialog.py (gui/util.py).
def _wrap(layout) -> QWidget:
    w = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    w.setLayout(layout)
    return w
