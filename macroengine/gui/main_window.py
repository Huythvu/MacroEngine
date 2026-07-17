"""MacroEngine main window: recorder controls, editable timeline, and the
vision-triggers panel.

Recorder/player/monitor callbacks arrive on non-GUI threads (pynput / worker
threads). They are marshaled back onto the GUI thread via the :class:`_Bridge`
QObject signals, which Qt delivers as queued connections.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.hotkeys import (
    DEFAULT_PANIC,
    DEFAULT_PLAY,
    DEFAULT_RECORD,
    HotkeyManager,
)
from ..core.player import Player
from ..core.recorder import Recorder
from ..models.macro import Macro
from ..models.trigger import Trigger, load_triggers, save_triggers
from ..vision.monitor import Monitor
from .macro_table import MacroTableModel, MacroTableView
from .trigger_dialog import TriggerDialog


class _Bridge(QObject):
    recorded = Signal(object)          # Macro
    playback_finished = Signal()
    trigger_fired = Signal(str)
    hotkey_record = Signal()
    hotkey_play = Signal()
    hotkey_panic = Signal()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MacroEngine")
        self.resize(900, 640)

        self._macro = Macro()
        self._model = MacroTableModel(self._macro)
        self._triggers: List[Trigger] = []

        self._recorder: Optional[Recorder] = None
        self._player = Player(on_finished=lambda: self._bridge.playback_finished.emit())
        self._monitor: Optional[Monitor] = None

        self._bridge = _Bridge()
        self._bridge.recorded.connect(self._on_recorded)
        self._bridge.playback_finished.connect(self._on_playback_finished)
        self._bridge.trigger_fired.connect(self._on_trigger_fired)
        self._bridge.hotkey_record.connect(self._toggle_record)
        self._bridge.hotkey_play.connect(self._toggle_play)
        self._bridge.hotkey_panic.connect(self._panic)

        self._build_ui()
        self._build_menu()

        self._hotkeys = HotkeyManager(
            on_record=lambda: self._bridge.hotkey_record.emit(),
            on_play=lambda: self._bridge.hotkey_play.emit(),
            on_panic=lambda: self._bridge.hotkey_panic.emit(),
        )
        self._hotkeys.start()
        self._set_status("Ready")

    # -- UI construction ----------------------------------------------------
    def _build_ui(self) -> None:
        # Recorder controls.
        self._btn_record = QPushButton(f"Record ({DEFAULT_RECORD})")
        self._btn_play = QPushButton(f"Play ({DEFAULT_PLAY})")
        self._btn_stop = QPushButton(f"Stop ({DEFAULT_PANIC})")
        self._btn_record.clicked.connect(self._toggle_record)
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_stop.clicked.connect(self._panic)

        self._loop = QSpinBox()
        self._loop.setRange(0, 99999)
        self._loop.setValue(1)
        self._loop.setToolTip("Number of loops (0 = repeat forever until Stop)")

        self._record_moves = QCheckBox("Record mouse moves")
        self._record_moves.setChecked(True)

        controls = QHBoxLayout()
        controls.addWidget(self._btn_record)
        controls.addWidget(self._btn_play)
        controls.addWidget(self._btn_stop)
        controls.addWidget(QLabel("Loops:"))
        controls.addWidget(self._loop)
        controls.addWidget(self._record_moves)
        controls.addStretch(1)

        # Macro timeline.
        self._table = MacroTableView(self._model)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addLayout(controls)
        left_layout.addWidget(self._table)

        # Triggers panel.
        right = self._build_triggers_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

    def _build_triggers_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("<b>Vision triggers</b>"))

        self._trigger_list = QListWidget()
        layout.addWidget(self._trigger_list, 1)

        btns = QHBoxLayout()
        btn_add = QPushButton("Add")
        btn_edit = QPushButton("Edit")
        btn_remove = QPushButton("Remove")
        btn_add.clicked.connect(self._add_trigger)
        btn_edit.clicked.connect(self._edit_trigger)
        btn_remove.clicked.connect(self._remove_trigger)
        for b in (btn_add, btn_edit, btn_remove):
            btns.addWidget(b)
        layout.addLayout(btns)

        self._btn_monitor = QPushButton("Start monitoring")
        self._btn_monitor.setCheckable(True)
        self._btn_monitor.clicked.connect(self._toggle_monitor)
        layout.addWidget(self._btn_monitor)

        return panel

    def _build_menu(self) -> None:
        m = self.menuBar().addMenu("&Macro")
        m.addAction("New", self._new_macro)
        m.addAction("Open…", self._open_macro)
        m.addAction("Save As…", self._save_macro)
        t = self.menuBar().addMenu("&Triggers")
        t.addAction("Open…", self._open_triggers)
        t.addAction("Save As…", self._save_triggers)

    # -- recorder / player --------------------------------------------------
    def _toggle_record(self) -> None:
        if self._recorder and self._recorder.running:
            macro = self._recorder.stop()
            self._recorder = None
            macro.loop_count = self._loop.value()
            self._bridge.recorded.emit(macro)
            self._btn_record.setText(f"Record ({DEFAULT_RECORD})")
            self._set_status(f"Recorded {len(macro.events)} events")
            return
        if self._player.running:
            return
        self._recorder = Recorder(record_mouse_move=self._record_moves.isChecked())
        self._recorder.start()
        self._btn_record.setText("Stop recording")
        self._set_status("Recording… press again or F9 to stop")

    def _on_recorded(self, macro: Macro) -> None:
        self._macro = macro
        self._model.set_events(self._macro.events)

    def _toggle_play(self) -> None:
        if self._player.running:
            self._panic()
            return
        if self._recorder and self._recorder.running:
            return
        if not self._macro.events:
            self._set_status("Nothing to play — record or open a macro first")
            return
        self._macro.loop_count = self._loop.value()
        self._btn_play.setText("Stop playing")
        self._set_status("Playing…")
        self._player.play(self._macro)

    def _on_playback_finished(self) -> None:
        self._btn_play.setText(f"Play ({DEFAULT_PLAY})")
        self._set_status("Playback finished")

    def _panic(self) -> None:
        self._player.stop()
        if self._monitor and self._monitor.running:
            self._monitor.stop()
            self._btn_monitor.setChecked(False)
            self._btn_monitor.setText("Start monitoring")
        self._set_status("Stopped")

    # -- triggers -----------------------------------------------------------
    def _refresh_triggers(self) -> None:
        self._trigger_list.clear()
        for t in self._triggers:
            item = QListWidgetItem(f"{'●' if t.enabled else '○'} {t.name} — {t.describe()}")
            self._trigger_list.addItem(item)

    def _add_trigger(self) -> None:
        dlg = TriggerDialog(parent=self)
        if dlg.exec():
            self._triggers.append(dlg.get_trigger())
            self._refresh_triggers()

    def _edit_trigger(self) -> None:
        row = self._trigger_list.currentRow()
        if row < 0:
            return
        dlg = TriggerDialog(trigger=self._triggers[row], parent=self)
        if dlg.exec():
            self._triggers[row] = dlg.get_trigger()
            self._refresh_triggers()

    def _remove_trigger(self) -> None:
        row = self._trigger_list.currentRow()
        if row >= 0:
            del self._triggers[row]
            self._refresh_triggers()

    def _toggle_monitor(self) -> None:
        if self._monitor and self._monitor.running:
            self._monitor.stop()
            self._monitor = None
            self._btn_monitor.setText("Start monitoring")
            self._set_status("Monitoring stopped")
            return
        if not self._triggers:
            self._btn_monitor.setChecked(False)
            self._set_status("Add a trigger before monitoring")
            return
        self._monitor = Monitor(
            self._triggers,
            on_fire=lambda t: self._bridge.trigger_fired.emit(t.name),
        )
        self._monitor.start()
        self._btn_monitor.setText("Stop monitoring")
        self._set_status("Monitoring…")

    def _on_trigger_fired(self, name: str) -> None:
        self._set_status(f"Trigger fired: {name}")

    # -- file ops -----------------------------------------------------------
    def _new_macro(self) -> None:
        self._macro = Macro()
        self._model.set_events(self._macro.events)
        self._set_status("New macro")

    def _open_macro(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open macro", "", "Macro files (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            self._macro = Macro.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self._model.set_events(self._macro.events)
        self._loop.setValue(self._macro.loop_count)
        self._set_status(f"Opened {path}")

    def _save_macro(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save macro", "macro.json", "Macro files (*.json)"
        )
        if not path:
            return
        self._macro.loop_count = self._loop.value()
        try:
            self._macro.save(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._set_status(f"Saved {path}")

    def _open_triggers(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open triggers", "", "Trigger files (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            self._triggers = load_triggers(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self._refresh_triggers()
        self._set_status(f"Opened {path}")

    def _save_triggers(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save triggers", "triggers.json", "Trigger files (*.json)"
        )
        if not path:
            return
        try:
            save_triggers(self._triggers, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._set_status(f"Saved {path}")

    # -- misc ---------------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def closeEvent(self, event) -> None:
        self._player.stop()
        if self._monitor and self._monitor.running:
            self._monitor.stop()
        if self._recorder and self._recorder.running:
            self._recorder.stop()
        self._hotkeys.stop()
        super().closeEvent(event)
