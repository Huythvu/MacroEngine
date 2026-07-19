"""The Routine tab: a library of saved routines beside an editor that builds and
runs a chain of macro / wait / vision steps."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
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
    STEP_IF_VISION,
    STEP_MACRO,
    STEP_WAIT,
    STEP_WAIT_VISION,
    Routine,
    RoutineStep,
)
from ..paths import macros_dir, routines_dir, safe_filename
from .editable_list import EditableListPanel
from .library_panel import LibraryPanel
from .routine_step_dialogs import (
    IfVisionStepDialog,
    MacroStepDialog,
    VisionStepDialog,
    WaitStepDialog,
)

_STEP_PREFIX = {
    STEP_MACRO: "▶", STEP_WAIT: "⏲", STEP_WAIT_VISION: "👁", STEP_IF_VISION: "⑂",
}


class _RunnerBridge(QObject):
    step = Signal(int, str)
    finished = Signal(str)


class RoutinePanel(QWidget):
    """Owns one routine at a time (like the recorder owns one macro), plus a
    library of saved routines from the per-user routines folder."""

    def __init__(
        self,
        status_cb,
        recorder_factory=None,
        on_macro_saved=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._status = status_cb
        # Called to create a configured core.Recorder — recording a new macro
        # section directly from this tab (saved to the library + added as a step).
        self._recorder_factory = recorder_factory
        self._on_macro_saved = on_macro_saved
        self._recorder = None
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
        root.addWidget(splitter)

        self._library.refresh()

    # -- library side --------------------------------------------------------
    def _build_library(self) -> QWidget:
        self._library = LibraryPanel(
            "Saved routines",
            directory=routines_dir,
            name_of=lambda p: Routine.load(p).name,
            on_open=self._load_routine,
            on_run=self._open_and_run,
            on_rename=self._routine_rename,
            on_duplicate=self._routine_duplicate,
        )
        return self._library

    def _routine_rename(self, path: Path, new_name: str) -> None:
        routine = Routine.load(path)
        routine.name = new_name
        new_path = routines_dir() / f"{safe_filename(new_name)}.json"
        routine.save(new_path)
        if new_path != path:
            path.unlink(missing_ok=True)
        if self._current_path == path:
            self._current_path = new_path
            self._name.setText(new_name)

    def _routine_duplicate(self, path: Path) -> None:
        routine = Routine.load(path)
        routine.name = f"{routine.name} copy"
        routine.save(routines_dir() / f"{safe_filename(routine.name)}.json")

    def _open_and_run(self, path: Path) -> None:
        self._load_routine(path)
        self._play()

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
        btn_save = QPushButton("Save…")
        btn_new.clicked.connect(self.new_routine)
        btn_save.clicked.connect(self._save_to_library)
        file_row.addWidget(btn_new)
        file_row.addWidget(btn_save)
        file_row.addStretch(1)
        layout.addLayout(file_row)

        layout.addWidget(QLabel("Steps (run top to bottom; untick to skip):"))
        self._steps_panel = EditableListPanel(
            self._routine.steps,
            describe=lambda s: f"{_STEP_PREFIX.get(s.type, '•')}  {s.describe()}",
            add_buttons=[
                ("+ Macro…", lambda: self._make_step(MacroStepDialog)),
                ("+ Wait…", lambda: self._make_step(WaitStepDialog)),
                ("+ Vision wait…", lambda: self._make_step(VisionStepDialog)),
                ("+ If…", lambda: self._make_step(IfVisionStepDialog)),
            ],
            on_edit=self._edit_step,
        )
        layout.addWidget(self._steps_panel, 1)

        # Record / Play / Stop — same controls as the Recorder tab. Record
        # captures a new macro section right here: it's saved to the macro
        # library and appended to the routine as a step.
        self._btn_record = QPushButton("⏺ Record step")
        self._btn_record.setCheckable(True)
        self._btn_record.setToolTip(
            "Record a new macro section; when you stop, it's saved to the "
            "library and added to the routine as a step."
        )
        self._btn_record.clicked.connect(self._toggle_record)
        self._btn_play = QPushButton("▶ Play")
        self._btn_play.setToolTip("Run the routine from the top")
        self._btn_play.clicked.connect(self._play)
        self._btn_stop = QPushButton("⏹ Stop")
        self._btn_stop.setToolTip("Stop the routine (or cancel recording)")
        self._btn_stop.clicked.connect(self.stop)
        run_row = QHBoxLayout()
        run_row.addWidget(self._btn_record)
        run_row.addWidget(self._btn_play)
        run_row.addWidget(self._btn_stop)
        layout.addLayout(run_row)
        return panel

    # -- inline recording ----------------------------------------------------
    @property
    def recording(self) -> bool:
        return self._recorder is not None and self._recorder.running

    def _toggle_record(self) -> None:
        if self.recording:
            self._finish_recording()
            return
        if self._recorder_factory is None or self.running:
            self._btn_record.setChecked(False)
            return
        self._recorder = self._recorder_factory()
        if self._recorder is None:  # e.g. the Recorder tab is already recording
            self._btn_record.setChecked(False)
            self._status("Recording is already active elsewhere")
            return
        self._recorder.start()
        self._btn_record.setText("⏺ Stop recording")
        self._btn_record.setChecked(True)
        self._status("Recording a routine step… press the button again to stop")

    def _finish_recording(self) -> None:
        macro = self._recorder.stop(trim_leading_click=True, trim_trailing_click=True)
        self._recorder = None
        self._btn_record.setText("⏺ Record step")
        self._btn_record.setChecked(False)
        if not macro.events:
            self._status("Nothing recorded")
            return
        default = f"{self._name.text() or 'routine'} step {len(self._routine.steps) + 1}"
        name, ok = QInputDialog.getText(
            self, "Save recorded step", "Name for this section:", text=default
        )
        if not ok or not name.strip():
            self._status("Recording discarded")
            return
        macro.name = name.strip()
        path = macros_dir() / f"{safe_filename(macro.name)}.json"
        try:
            macro.save(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._routine.steps.append(
            RoutineStep(type=STEP_MACRO, name=macro.name, macro_path=str(path))
        )
        self._steps_panel.refresh()
        if self._on_macro_saved is not None:
            self._on_macro_saved()
        self._status(f"Recorded '{macro.name}' ({len(macro.events)} events) — added as a step")

    def _cancel_recording(self) -> None:
        if self.recording:
            self._recorder.stop()
        self._recorder = None
        self._btn_record.setText("⏺ Record step")
        self._btn_record.setChecked(False)

    # -- public (main window menu calls these) -------------------------------
    @property
    def running(self) -> bool:
        return self._runner is not None and self._runner.running

    def stop(self) -> None:
        if self.recording:
            self._cancel_recording()
            self._status("Recording cancelled")
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
        self._steps_panel.set_items(self._routine.steps)
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
        self._steps_panel.set_items(self._routine.steps)
        self._status(f"Opened routine '{self._routine.name}'")

    def _save_to_library(self) -> None:
        routine = self.current_routine()
        path = routines_dir() / f"{safe_filename(routine.name)}.json"
        # Guard against silently clobbering a different saved routine that
        # happens to share this name. Re-saving the one we opened is fine.
        if path.exists() and path != self._current_path:
            if QMessageBox.question(
                self, "Overwrite routine?",
                f"A saved routine named '{routine.name}' already exists.\n"
                "Overwrite it?",
            ) != QMessageBox.Yes:
                self._status("Save cancelled — rename the routine to keep both")
                return
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
    def _make_step(self, dialog_cls):
        dlg = dialog_cls(parent=self)
        return dlg.get_step() if dlg.exec() else None

    def _edit_step(self, step):
        dialog_cls = {
            STEP_MACRO: MacroStepDialog,
            STEP_WAIT: WaitStepDialog,
            STEP_WAIT_VISION: VisionStepDialog,
            STEP_IF_VISION: IfVisionStepDialog,
        }.get(step.type)
        if dialog_cls is None:
            return None
        dlg = dialog_cls(step=step, parent=self)
        return dlg.get_step() if dlg.exec() else None

    # -- running -------------------------------------------------------------
    def _play(self) -> None:
        if self.running or self.recording:
            return
        routine = self.current_routine()
        if not any(s.enabled for s in routine.steps):
            self._status("Add (and enable) at least one step first")
            return
        self._runner = RoutineRunner(
            on_step=lambda i, text: self._bridge.step.emit(i, text),
            on_finished=lambda reason: self._bridge.finished.emit(reason),
        )
        self._btn_play.setEnabled(False)
        self._status("Routine running…")
        self._runner.run(routine)

    def _on_step(self, index: int, text: str) -> None:
        self._steps_panel.highlight(index)
        self._status(f"Routine step {index + 1}: {text}")

    def _on_finished(self, reason: str) -> None:
        self._btn_play.setEnabled(True)
        self._status(reason)
