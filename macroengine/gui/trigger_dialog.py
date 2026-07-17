"""Dialog to create or edit a single vision :class:`Trigger`.

Composed from the shared building blocks: :class:`ConditionWidget` (the vision
half) and :class:`ActionWidget` (what to do when it fires).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ..models import actions
from ..models.trigger import DETECT_TEMPLATE, Trigger
from .action_widget import ActionWidget
from .condition_widget import ConditionWidget


class TriggerDialog(QDialog):
    def __init__(self, trigger: Optional[Trigger] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vision Trigger")
        self._trigger = trigger or Trigger()

        self._name = QLineEdit(self._trigger.name)
        self._condition_widget = ConditionWidget(self._trigger)
        self._action_widget = ActionWidget(
            allowed=actions.ALL_ACTIONS,
            action=self._trigger.action,
            key=self._trigger.action_key,
            text=self._trigger.action_text,
            x=self._trigger.action_x,
            y=self._trigger.action_y,
            button=self._trigger.action_button,
            macro_path=self._trigger.action_macro_path,
        )

        self._cooldown = QDoubleSpinBox()
        self._cooldown.setRange(0.0, 3600.0)
        self._cooldown.setDecimals(2)
        self._cooldown.setSingleStep(0.1)
        self._cooldown.setValue(self._trigger.cooldown_s)

        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Cooldown (s):", self._cooldown)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(self._condition_widget)
        root.addWidget(self._action_widget)
        root.addLayout(form)
        root.addWidget(buttons)

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
        if (
            self._action_widget.action == actions.CLICK_MATCH
            and self._condition_widget.detection_kind != DETECT_TEMPLATE
        ):
            QMessageBox.warning(
                self, "Needs template detection",
                "'Click on the found image' needs Template detection — color mode "
                "has no image to locate.",
            )
            return
        self.accept()

    def get_trigger(self) -> Trigger:
        t = self._trigger
        t.name = self._name.text() or "Trigger"
        self._condition_widget.apply_to(t)
        v = self._action_widget.values()
        t.action = v["action"]
        t.action_key = v["key"]
        t.action_text = v["text"]
        t.action_x, t.action_y, t.action_button = v["x"], v["y"], v["button"]
        t.action_macro_path = v["macro_path"]
        t.cooldown_s = float(self._cooldown.value())
        return t
