"""The Routine tab: build and run a chain of macro / wait / vision steps."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.routine_runner import RoutineRunner
from ..models.routine import (
    STEP_MACRO,
    STEP_WAIT,
    STEP_WAIT_VISION,
    Routine,
)
from .routine_step_dialogs import MacroStepDialog, VisionStepDialog, WaitStepDialog

_STEP_PREFIX = {STEP_MACRO: "▶", STEP_WAIT: "⏲", STEP_WAIT_VISION: "👁"}


class _RunnerBridge(QObject):
    step = Signal(int, str)
    finished = Signal(str)


class RoutinePanel(QWidget):
    """Owns one routine at a time (like the recorder owns one macro)."""

    def __init__(self, status_cb, parent=None) -> None:
        super().__init__(parent)
        self._status = status_cb
        self._routine = Routine()
        self._runner: Optional[RoutineRunner] = None
        self._bridge = _RunnerBridge()
        self._bridge.step.connect(self._on_step)
        self._bridge.finished.connect(self._on_finished)

        self._name = QLineEdit(self._routine.name)
        self._name.setPlaceholderText("Routine name")
        self._loops = QSpinBox()
        self._loops.setRange(0, 99999)
        self._loops.setValue(self._routine.loop_count)
        self._loops.setToolTip("Times to repeat the whole routine (0 = forever)")
        top = QHBoxLayout()
        top.addWidget(QLabel("Name:"))
        top.addWidget(self._name, 1)
        top.addWidget(QLabel("Loops:"))
        top.addWidget(self._loops)

        self._list = QListWidget()
        self._list.itemChanged.connect(self._check_changed)

        add_row = QHBoxLayout()
        btn_macro = QPushButton("+ Macro…")
        btn_wait = QPushButton("+ Wait…")
        btn_vision = QPushButton("+ Vision wait…")
        btn_macro.clicked.connect(lambda: self._add(MacroStepDialog))
        btn_wait.clicked.connect(lambda: self._add(WaitStepDialog))
        btn_vision.clicked.connect(lambda: self._add(VisionStepDialog))
        for b in (btn_macro, btn_wait, btn_vision):
            add_row.addWidget(b)
        add_row.addStretch(1)

        edit_row = QHBoxLayout()
        btn_edit = QPushButton("Edit…")
        btn_remove = QPushButton("Remove")
        btn_up = QPushButton("Move Up")
        btn_down = QPushButton("Move Down")
        btn_edit.clicked.connect(self._edit)
        btn_remove.clicked.connect(self._remove)
        btn_up.clicked.connect(lambda: self._move(-1))
        btn_down.clicked.connect(lambda: self._move(1))
        for b in (btn_edit, btn_remove, btn_up, btn_down):
            edit_row.addWidget(b)
        edit_row.addStretch(1)

        self._btn_run = QPushButton("Run routine")
        self._btn_run.setCheckable(True)
        self._btn_run.clicked.connect(self._toggle_run)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(QLabel("Steps (run top to bottom; untick to skip):"))
        root.addWidget(self._list, 1)
        root.addLayout(add_row)
        root.addLayout(edit_row)
        root.addWidget(self._btn_run)

        self._refresh()

    # -- public (main window calls these) ------------------------------------
    @property
    def running(self) -> bool:
        return self._runner is not None and self._runner.running

    def stop(self) -> None:
        if self._runner is not None:
            self._runner.stop()

    def current_routine(self) -> Routine:
        self._routine.name = self._name.text() or "Routine"
        self._routine.loop_count = self._loops.value()
        return self._routine

    def new_routine(self) -> None:
        self._routine = Routine()
        self._name.setText(self._routine.name)
        self._loops.setValue(self._routine.loop_count)
        self._refresh()

    def open_routine(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open routine", "", "Routine files (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            self._routine = Routine.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self._name.setText(self._routine.name)
        self._loops.setValue(self._routine.loop_count)
        self._refresh()
        self._status(f"Opened routine {path}")

    def save_routine(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save routine", "routine.json", "Routine files (*.json)"
        )
        if not path:
            return
        try:
            self.current_routine().save(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._status(f"Saved routine {path}")

    # -- list handling --------------------------------------------------------
    def _refresh(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for step in self._routine.steps:
            prefix = _STEP_PREFIX.get(step.type, "•")
            item = QListWidgetItem(f"{prefix}  {step.describe()}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if step.enabled else Qt.Unchecked)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _check_changed(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if 0 <= row < len(self._routine.steps):
            self._routine.steps[row].enabled = item.checkState() == Qt.Checked

    def _add(self, dialog_cls) -> None:
        dlg = dialog_cls(parent=self)
        if dlg.exec():
            self._routine.steps.append(dlg.get_step())
            self._refresh()

    def _edit(self) -> None:
        row = self._list.currentRow()
        if not (0 <= row < len(self._routine.steps)):
            return
        step = self._routine.steps[row]
        dialog_cls = {
            STEP_MACRO: MacroStepDialog,
            STEP_WAIT: WaitStepDialog,
            STEP_WAIT_VISION: VisionStepDialog,
        }.get(step.type)
        if dialog_cls is None:
            return
        dlg = dialog_cls(step=step, parent=self)
        if dlg.exec():
            self._routine.steps[row] = dlg.get_step()
            self._refresh()
            self._list.setCurrentRow(row)

    def _remove(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._routine.steps):
            del self._routine.steps[row]
            self._refresh()

    def _move(self, delta: int) -> None:
        row = self._list.currentRow()
        target = row + delta
        steps = self._routine.steps
        if not (0 <= row < len(steps)) or not (0 <= target < len(steps)):
            return
        steps[row], steps[target] = steps[target], steps[row]
        self._refresh()
        self._list.setCurrentRow(target)

    # -- running --------------------------------------------------------------
    def _toggle_run(self) -> None:
        if self.running:
            self.stop()
            return
        routine = self.current_routine()
        if not any(s.enabled for s in routine.steps):
            self._btn_run.setChecked(False)
            self._status("Add (and enable) at least one step first")
            return
        self._runner = RoutineRunner(
            on_step=lambda i, text: self._bridge.step.emit(i, text),
            on_finished=lambda reason: self._bridge.finished.emit(reason),
        )
        self._btn_run.setText("Stop routine")
        self._btn_run.setChecked(True)
        self._status("Routine running…")
        self._runner.run(routine)

    def _on_step(self, index: int, text: str) -> None:
        if 0 <= index < self._list.count():
            self._list.setCurrentRow(index)
        self._status(f"Routine step {index + 1}: {text}")

    def _on_finished(self, reason: str) -> None:
        self._btn_run.setText("Run routine")
        self._btn_run.setChecked(False)
        self._status(reason)
