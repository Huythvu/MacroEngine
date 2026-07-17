"""Dialogs for the three routine step types (macro / wait / wait-for-vision)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..models.routine import (
    STEP_MACRO,
    STEP_WAIT,
    STEP_WAIT_VISION,
    TIMEOUT_CONTINUE,
    TIMEOUT_STOP,
    RoutineStep,
)
from ..models.macro import Macro
from ..models.trigger import DETECT_TEMPLATE
from ..paths import macros_dir
from .condition_widget import ConditionWidget
from .util import wrap


class MacroStepDialog(QDialog):
    def __init__(self, step: Optional[RoutineStep] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Macro Step")
        self._step = step or RoutineStep(type=STEP_MACRO)

        self._name = QLineEdit(self._step.name)
        self._name.setPlaceholderText("optional label, e.g. 'walk to vendor'")

        # Pick from the saved-macro library, or browse to any file.
        self._library = QComboBox()
        self._library.addItem("— pick from library —", "")
        for p in sorted(macros_dir().glob("*.json")):
            try:
                name = Macro.load(p).name or p.stem
            except Exception:  # noqa: BLE001
                name = p.stem
            self._library.addItem(name, str(p))
        self._library.currentIndexChanged.connect(self._pick_from_library)

        self._path = QLineEdit(self._step.macro_path)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self._path, 1)
        path_row.addWidget(btn_browse)

        self._loops = QSpinBox()
        self._loops.setRange(0, 99999)
        self._loops.setValue(self._step.loop_override)
        self._loops.setToolTip("0 = play the macro as it was saved")
        self._loops.setSpecialValueText("as saved")

        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("From library:", self._library)
        form.addRow("Macro file:", wrap(path_row))
        form.addRow("Loops:", self._loops)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _pick_from_library(self, index: int) -> None:
        path = self._library.currentData()
        if path:
            self._path.setText(path)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select macro", str(macros_dir()), "Macro files (*.json);;All files (*)"
        )
        if path:
            self._path.setText(path)

    def _accept(self) -> None:
        if not self._path.text().strip():
            QMessageBox.warning(self, "Missing macro", "Choose a macro file first.")
            return
        self.accept()

    def get_step(self) -> RoutineStep:
        s = self._step
        s.type = STEP_MACRO
        s.name = self._name.text()
        s.macro_path = self._path.text().strip()
        s.loop_override = int(self._loops.value())
        return s


class WaitStepDialog(QDialog):
    def __init__(self, step: Optional[RoutineStep] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Wait Step")
        self._step = step or RoutineStep(type=STEP_WAIT)

        self._wait = QDoubleSpinBox()
        self._wait.setRange(0.0, 86400.0)
        self._wait.setDecimals(2)
        self._wait.setSingleStep(0.5)
        self._wait.setValue(self._step.wait_s)

        self._jitter = QDoubleSpinBox()
        self._jitter.setRange(0.0, 3600.0)
        self._jitter.setDecimals(2)
        self._jitter.setSingleStep(0.1)
        self._jitter.setValue(self._step.jitter_s)
        self._jitter.setToolTip("Random +/- added to the wait (0 = exact)")

        form = QFormLayout()
        form.addRow("Wait (s):", self._wait)
        form.addRow("Jitter ± (s):", self._jitter)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def get_step(self) -> RoutineStep:
        s = self._step
        s.type = STEP_WAIT
        s.wait_s = float(self._wait.value())
        s.jitter_s = float(self._jitter.value())
        return s


class VisionStepDialog(QDialog):
    def __init__(self, step: Optional[RoutineStep] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Wait-for-Vision Step")
        self._step = step or RoutineStep(type=STEP_WAIT_VISION)

        self._name = QLineEdit(self._step.name)
        self._name.setPlaceholderText("optional label, e.g. 'loading finished'")
        self._condition_widget = ConditionWidget(self._step)

        self._timeout = QDoubleSpinBox()
        self._timeout.setRange(0.0, 86400.0)
        self._timeout.setDecimals(1)
        self._timeout.setSingleStep(5.0)
        self._timeout.setValue(self._step.timeout_s)
        self._timeout.setSpecialValueText("wait forever")
        self._timeout.setToolTip("0 = wait forever (Esc still stops the routine)")

        self._on_timeout = QComboBox()
        self._on_timeout.addItem("Stop the routine", TIMEOUT_STOP)
        self._on_timeout.addItem("Continue anyway", TIMEOUT_CONTINUE)
        self._on_timeout.setCurrentIndex(
            0 if self._step.on_timeout == TIMEOUT_STOP else 1
        )

        self._click_match = QCheckBox("Click where the image was found")
        self._click_match.setChecked(self._step.click_on_match)
        self._click_match.setToolTip(
            "After the condition is met, left-click the center of the found "
            "reference — e.g. wait for an 'Accept' button, then click it. "
            "Template detection only."
        )

        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Timeout (s):", self._timeout)
        form.addRow("On timeout:", self._on_timeout)
        form.addRow("", self._click_match)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self)
        root.addWidget(self._condition_widget)
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
            self._click_match.isChecked()
            and self._condition_widget.detection_kind != DETECT_TEMPLATE
        ):
            QMessageBox.warning(
                self, "Needs template detection",
                "'Click where the image was found' needs Template detection — "
                "color mode has no image to locate.",
            )
            return
        self.accept()

    def get_step(self) -> RoutineStep:
        s = self._step
        s.type = STEP_WAIT_VISION
        s.name = self._name.text()
        self._condition_widget.apply_to(s)
        s.timeout_s = float(self._timeout.value())
        s.on_timeout = self._on_timeout.currentData()
        s.click_on_match = self._click_match.isChecked()
        return s
