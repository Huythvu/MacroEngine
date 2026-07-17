"""Dialog to create or edit a single :class:`AutoInput` (a timed repeater)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from ..models import actions
from ..models.autoinput import AutoInput
from .action_widget import ActionWidget

# Auto inputs have no reference template, so no click-on-match.
_AUTO_ACTIONS = (actions.PRESS_KEY, actions.TYPE_TEXT, actions.CLICK_AT, actions.RUN_MACRO)


class AutoInputDialog(QDialog):
    def __init__(self, auto: Optional[AutoInput] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto Input")
        self._auto = auto or AutoInput()

        self._name = QLineEdit(self._auto.name)
        self._action_widget = ActionWidget(
            allowed=_AUTO_ACTIONS,
            action=self._auto.action,
            key=self._auto.key,
            text=self._auto.text,
            x=self._auto.x,
            y=self._auto.y,
            button=self._auto.button,
            macro_path=self._auto.macro_path,
        )

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
        form.addRow("Interval (s):", self._interval)
        form.addRow("Jitter ± (s):", self._jitter)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(self._action_widget)
        root.addLayout(form)
        root.addWidget(buttons)

    def get_auto(self) -> AutoInput:
        a = self._auto
        a.name = self._name.text() or "Auto input"
        v = self._action_widget.values()
        a.action = v["action"]
        a.key = v["key"]
        a.text = v["text"]
        a.x, a.y, a.button = v["x"], v["y"], v["button"]
        a.macro_path = v["macro_path"]
        a.interval_s = float(self._interval.value())
        a.jitter_s = float(self._jitter.value())
        return a
