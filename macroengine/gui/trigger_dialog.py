"""Dialog to create or edit a single vision :class:`Trigger`.

The vision half (region/detection/capture/preview/test) lives in the shared
:class:`ConditionWidget`; this dialog adds the trigger's name, action, and
cooldown.
"""

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
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models.trigger import (
    ACTION_PRESS_KEY,
    ACTION_RUN_MACRO,
    DETECT_TEMPLATE,
    Trigger,
)
from .condition_widget import ConditionWidget, _wrap
from .key_capture import KeyCaptureEdit


class TriggerDialog(QDialog):
    def __init__(self, trigger: Optional[Trigger] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vision Trigger")
        self._trigger = trigger or Trigger()

        self._name = QLineEdit(self._trigger.name)
        self._condition_widget = ConditionWidget(self._trigger)

        # Action.
        self._action = QComboBox()
        self._action.addItem("Press key", ACTION_PRESS_KEY)
        self._action.addItem("Run macro", ACTION_RUN_MACRO)
        self._action.setCurrentIndex(
            0 if self._trigger.action == ACTION_PRESS_KEY else 1
        )
        self._action.currentIndexChanged.connect(self._sync_action)
        self._action_key = KeyCaptureEdit(self._trigger.action_key)
        self._action_macro = QLineEdit(self._trigger.action_macro_path)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_macro)
        macro_row = QHBoxLayout()
        macro_row.addWidget(self._action_macro, 1)
        macro_row.addWidget(btn_browse)

        self._cooldown = QDoubleSpinBox()
        self._cooldown.setRange(0.0, 3600.0)
        self._cooldown.setDecimals(2)
        self._cooldown.setSingleStep(0.1)
        self._cooldown.setValue(self._trigger.cooldown_s)

        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Action:", self._action)
        self._key_label = QLabel("Key:")
        form.addRow(self._key_label, self._action_key)
        self._macro_label = QLabel("Macro:")
        self._macro_widget = _wrap(macro_row)
        form.addRow(self._macro_label, self._macro_widget)
        form.addRow("Cooldown (s):", self._cooldown)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(self._condition_widget)
        root.addLayout(form)
        root.addWidget(buttons)
        self._sync_action()

    def _sync_action(self) -> None:
        is_key = self._action.currentData() == ACTION_PRESS_KEY
        self._key_label.setVisible(is_key)
        self._action_key.setVisible(is_key)
        self._macro_label.setVisible(not is_key)
        self._macro_widget.setVisible(not is_key)

    def _browse_macro(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select macro", "", "Macro files (*.json);;All files (*)"
        )
        if path:
            self._action_macro.setText(path)

    def _accept(self) -> None:
        if (
            self._condition_widget.detection_kind == DETECT_TEMPLATE
            and not self._condition_widget.has_template
        ):
            QMessageBox.warning(
                self, "Missing snapshot",
                "Capture a reference snapshot from the region first.",
            )
            return
        self.accept()

    def get_trigger(self) -> Trigger:
        t = self._trigger
        t.name = self._name.text() or "Trigger"
        self._condition_widget.apply_to(t)
        t.action = self._action.currentData()
        t.action_key = self._action_key.keystroke() or "1"
        t.action_macro_path = self._action_macro.text()
        t.cooldown_s = float(self._cooldown.value())
        return t
