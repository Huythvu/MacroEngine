"""The Routine tab: a library of saved routines beside an editor that builds and
runs a chain of macro / wait / vision steps."""

from __future__ import annotations

from pathlib import Path
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
    QSplitter,
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
from ..paths import routines_dir, safe_filename
from .library_panel import LibraryPanel
from .routine_step_dialogs import MacroStepDialog, VisionStepDialog, WaitStepDialog
from .util import intro

_STEP_PREFIX = {STEP_MACRO: "▶", STEP_WAIT: "⏲", STEP_WAIT_VISION: "👁"}


class _RunnerBridge(QObject):
    step = Signal(int, str)
    finished = Signal(str)


class RoutinePanel(QWidget):
    """Owns one routine at a time (like the recorder owns one macro), plus a
    library of saved routines from the per-user routines folder."""

    def __init__(self, status_cb, parent=None) -> None:
        super().__init__(parent)
        self._status = status_cb
        self._routine = Routine()
        self._current_path: Optional[Path] = None
        self._runner: Optional[RoutineRunner] = None
        self._bridge = _RunnerBridge()
        self._bridge.step.connect(self._on_step)
        self._bridge.finished.connect(self._on_finished)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_library())
        splitter.addWidget(self._build_editor())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        root = QVBoxLayout(self)
        root.addWidget(intro(
            "Chain small saved macros into one sequence (e.g. a daily): play a macro → "
            "wait → wait until the screen shows something → play the next. Pick a saved "
            "routine on the left and <b>Open &amp; Run</b>, or build a new one on the right."
        ))
        root.addWidget(splitter)

        self._library.refresh()
        self._refresh_steps()

    # -- library side --------------------------------------------------------
    def _build_library(self) -> QWidget:
        self._library = LibraryPanel(
            "Saved routines",
            directory=routines_dir,
            name_of=lambda p: Routine.load(p).name,
            on_open=self._load_routine,
            on_run=self._open_and_run,
        )
        return self._library

    def _open_and_run(self, path: Path) -> None:
        self._load_routine(path)
        if not self.running:
            self._toggle_run()

    # -- editor side ---------------------------------------------------------
    def _build_editor(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

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
        layout.addLayout(top)

        file_row = QHBoxLayout()
        btn_new = QPushButton("New")
        btn_save = QPushButton("Save to library")
        btn_new.clicked.connect(self.new_routine)
        btn_save.clicked.connect(self._save_to_library)
        file_row.addWidget(btn_new)
        file_row.addWidget(btn_save)
        file_row.addStretch(1)
        layout.addLayout(file_row)

        layout.addWidget(QLabel("Steps (run top to bottom; untick to skip):"))
        self._list = QListWidget()
        self._list.itemChanged.connect(self._check_changed)
        layout.addWidget(self._list, 1)

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
        layout.addLayout(add_row)

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
        layout.addLayout(edit_row)

        self._btn_run = QPushButton("Run routine")
        self._btn_run.setCheckable(True)
        self._btn_run.clicked.connect(self._toggle_run)
        layout.addWidget(self._btn_run)
        return panel

    # -- public (main window menu calls these) -------------------------------
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
        self._current_path = None
        self._name.setText(self._routine.name)
        self._loops.setValue(self._routine.loop_count)
        self._refresh_steps()
        self._status("New routine")

    def open_routine(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open routine", str(routines_dir()), "Routine files (*.json);;All files (*)"
        )
        if path:
            self._load_routine(Path(path))

    def save_routine(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save routine", str(routines_dir() / "routine.json"),
            "Routine files (*.json)",
        )
        if path:
            self._save_routine_to(Path(path))

    def _load_routine(self, path: Path) -> None:
        try:
            self._routine = Routine.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self._current_path = path
        self._name.setText(self._routine.name)
        self._loops.setValue(self._routine.loop_count)
        self._refresh_steps()
        self._status(f"Opened routine '{self._routine.name}'")

    def _save_to_library(self) -> None:
        routine = self.current_routine()
        path = routines_dir() / f"{safe_filename(routine.name)}.json"
        self._save_routine_to(path)
        self._library.refresh()

    def _save_routine_to(self, path: Path) -> None:
        try:
            self.current_routine().save(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._current_path = path
        self._status(f"Saved routine '{self._routine.name}'")

    # -- step list -----------------------------------------------------------
    def _refresh_steps(self) -> None:
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
            self._refresh_steps()

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
            self._refresh_steps()
            self._list.setCurrentRow(row)

    def _remove(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._routine.steps):
            del self._routine.steps[row]
            self._refresh_steps()

    def _move(self, delta: int) -> None:
        row = self._list.currentRow()
        target = row + delta
        steps = self._routine.steps
        if not (0 <= row < len(steps)) or not (0 <= target < len(steps)):
            return
        steps[row], steps[target] = steps[target], steps[row]
        self._refresh_steps()
        self._list.setCurrentRow(target)

    # -- running -------------------------------------------------------------
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
