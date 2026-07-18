"""Dialogs for the routine step types (macro / wait / wait-for-vision / if)."""

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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..core.recorder import Recorder
from ..models import actions
from ..models.actions import Action
from ..models.routine import (
    STEP_IF_VISION,
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
from .action_widget import ActionWidget
from .condition_widget import ConditionWidget
from .util import wrap

# Actions offered in the If-step branches (no template here, so no click-match).
_IF_ACTIONS = (actions.NONE, actions.PRESS_KEY, actions.TYPE_TEXT,
               actions.CLICK_AT, actions.RUN_MACRO)

_SOURCE_SAVED = "saved"
_SOURCE_INLINE = "inline"


class MacroStepDialog(QDialog):
    def __init__(self, step: Optional[RoutineStep] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Macro Step")
        self._step = step or RoutineStep(type=STEP_MACRO)
        self._recorder: Optional[Recorder] = None
        self._recorded: Optional[Macro] = (
            Macro.from_dict(self._step.inline_macro) if self._step.inline_macro else None
        )

        self._name = QLineEdit(self._step.name)
        self._name.setPlaceholderText("optional label, e.g. 'walk to vendor'")

        # Source: a saved macro, or one recorded right here (inline).
        self._source = QComboBox()
        self._source.addItem("Saved macro", _SOURCE_SAVED)
        self._source.addItem("Record inline", _SOURCE_INLINE)
        self._source.setCurrentIndex(1 if self._recorded is not None else 0)
        self._source.currentIndexChanged.connect(self._sync_source)

        # -- saved-macro widgets --
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
        saved_form = QFormLayout()
        saved_form.addRow("From library:", self._library)
        saved_form.addRow("Macro file:", wrap(path_row))
        self._saved_group = QGroupBox("Saved macro")
        self._saved_group.setLayout(saved_form)

        # -- inline-record widgets --
        self._btn_record = QPushButton("● Record")
        self._btn_record.clicked.connect(self._toggle_record)
        self._rec_status = QLabel()
        self._rec_moves = QCheckBox("Record mouse moves")
        self._rec_moves.setChecked(True)
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear_recording)
        rec_row = QHBoxLayout()
        rec_row.addWidget(self._btn_record)
        rec_row.addWidget(btn_clear)
        rec_row.addWidget(self._rec_status, 1)
        inline_col = QVBoxLayout()
        inline_col.addLayout(rec_row)
        inline_col.addWidget(self._rec_moves)
        inline_col.addWidget(QLabel(
            "Click Record, do the actions in your game, then Record again to stop."
        ))
        self._inline_group = QGroupBox("Recorded macro")
        self._inline_group.setLayout(inline_col)

        self._loops = QSpinBox()
        self._loops.setRange(0, 99999)
        self._loops.setValue(self._step.loop_override)
        self._loops.setToolTip("0 = play the macro as it was saved / recorded")
        self._loops.setSpecialValueText("as saved")

        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Source:", self._source)
        form.addRow("Loops:", self._loops)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.accepted.connect(self._accept)
        self._buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self._saved_group)
        root.addWidget(self._inline_group)
        root.addWidget(self._buttons)
        self._update_rec_status()
        self._sync_source()

    # -- saved --------------------------------------------------------------
    def _pick_from_library(self, _index: int) -> None:
        path = self._library.currentData()
        if path:
            self._path.setText(path)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select macro", str(macros_dir()), "Macro files (*.json);;All files (*)"
        )
        if path:
            self._path.setText(path)

    # -- inline recording ---------------------------------------------------
    def _toggle_record(self) -> None:
        if self._recorder and self._recorder.running:
            # Trim the clicks on this Record button at both ends.
            self._recorded = self._recorder.stop(
                trim_leading_click=True, trim_trailing_click=True
            )
            self._recorder = None
            self._btn_record.setText("● Record")
            self._buttons.button(QDialogButtonBox.Ok).setEnabled(True)
            self._update_rec_status()
            return
        self._recorder = Recorder(record_mouse_move=self._rec_moves.isChecked())
        self._recorder.start()
        self._btn_record.setText("■ Stop")
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self._rec_status.setText("recording… go to your game")

    def _clear_recording(self) -> None:
        if self._recorder and self._recorder.running:
            self._recorder.stop()
            self._recorder = None
            self._btn_record.setText("● Record")
            self._buttons.button(QDialogButtonBox.Ok).setEnabled(True)
        self._recorded = None
        self._update_rec_status()

    def _update_rec_status(self) -> None:
        if self._recorded is not None:
            self._rec_status.setText(f"recorded: {len(self._recorded.events)} events")
        else:
            self._rec_status.setText("nothing recorded yet")

    def _sync_source(self) -> None:
        inline = self._source.currentData() == _SOURCE_INLINE
        self._saved_group.setVisible(not inline)
        self._inline_group.setVisible(inline)

    def _accept(self) -> None:
        if self._recorder and self._recorder.running:
            QMessageBox.warning(self, "Still recording", "Stop the recording first.")
            return
        if self._source.currentData() == _SOURCE_INLINE:
            if self._recorded is None or not self._recorded.events:
                QMessageBox.warning(self, "No recording", "Record a macro first.")
                return
        elif not self._path.text().strip():
            QMessageBox.warning(self, "Missing macro", "Choose a macro file first.")
            return
        self.accept()

    def reject(self) -> None:  # stop a dangling recorder on cancel
        if self._recorder and self._recorder.running:
            self._recorder.stop()
            self._recorder = None
        super().reject()

    def get_step(self) -> RoutineStep:
        s = self._step
        s.type = STEP_MACRO
        s.name = self._name.text()
        s.loop_override = int(self._loops.value())
        if self._source.currentData() == _SOURCE_INLINE:
            s.inline_macro = self._recorded.to_dict() if self._recorded else None
            s.macro_path = ""
        else:
            s.inline_macro = None
            s.macro_path = self._path.text().strip()
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


class IfVisionStepDialog(QDialog):
    """A one-shot decision: check a vision condition now, run one action if it
    holds and a different action if not, then continue the routine."""

    def __init__(self, step: Optional[RoutineStep] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("If-Vision Step")
        self._step = step or RoutineStep(type=STEP_IF_VISION)

        self._name = QLineEdit(self._step.name)
        self._name.setPlaceholderText("optional label, e.g. 'low HP?'")
        self._condition_widget = ConditionWidget(self._step)

        self._then = self._make_action_widget(self._step.then_action)
        self._else = self._make_action_widget(self._step.else_action)
        then_group = QGroupBox("If the condition HOLDS → do")
        then_group.setLayout(_single(self._then))
        else_group = QGroupBox("Otherwise → do")
        else_group.setLayout(_single(self._else))

        form = QFormLayout()
        form.addRow("Name:", self._name)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self._condition_widget)
        root.addWidget(then_group)
        root.addWidget(else_group)
        root.addWidget(buttons)

    @staticmethod
    def _make_action_widget(action: Action) -> ActionWidget:
        return ActionWidget(
            allowed=_IF_ACTIONS,
            action=action.kind,
            key=action.key,
            text=action.text,
            x=action.x,
            y=action.y,
            button=action.button,
            macro_path=action.macro_path,
        )

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

    @staticmethod
    def _action_from_widget(widget: ActionWidget) -> Action:
        v = widget.values()
        return Action(
            kind=v["action"], key=v["key"], text=v["text"],
            x=v["x"], y=v["y"], button=v["button"], macro_path=v["macro_path"],
        )

    def get_step(self) -> RoutineStep:
        s = self._step
        s.type = STEP_IF_VISION
        s.name = self._name.text()
        self._condition_widget.apply_to(s)
        s.then_action = self._action_from_widget(self._then)
        s.else_action = self._action_from_widget(self._else)
        return s


def _single(widget) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setContentsMargins(6, 6, 6, 6)
    box.addWidget(widget)
    return box
