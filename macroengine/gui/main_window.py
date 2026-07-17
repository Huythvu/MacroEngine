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
from ..core.autorunner import AutoRunner
from ..core.player import Player
from ..core.recorder import Recorder
from ..models.autoinput import AutoInput
from ..models.buff import BuffGroup
from ..models.macro import Macro
from ..models.store import load_watchers, save_watchers
from ..models.trigger import Trigger
from ..vision.monitor import Monitor
from .auto_input_dialog import AutoInputDialog
from .buff_group_dialog import BuffGroupDialog
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
        self._groups: List[BuffGroup] = []
        self._rows: List[tuple] = []
        self._auto_inputs: List[AutoInput] = []
        self._auto_runner: Optional[AutoRunner] = None
        self._record_started_from_button = False

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
        self._btn_record.clicked.connect(lambda: self._toggle_record(from_button=True))
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
        layout.addWidget(QLabel("<b>Vision triggers &amp; buff groups</b>"))

        self._trigger_list = QListWidget()
        layout.addWidget(self._trigger_list, 1)

        btns = QHBoxLayout()
        btn_add = QPushButton("Add Trigger")
        btn_group = QPushButton("Add Buff Group")
        btn_edit = QPushButton("Edit")
        btn_remove = QPushButton("Remove")
        btn_add.clicked.connect(self._add_trigger)
        btn_group.clicked.connect(self._add_group)
        btn_edit.clicked.connect(self._edit_selected)
        btn_remove.clicked.connect(self._remove_selected)
        for b in (btn_add, btn_group, btn_edit, btn_remove):
            btns.addWidget(b)
        layout.addLayout(btns)

        self._btn_monitor = QPushButton("Start monitoring")
        self._btn_monitor.setCheckable(True)
        self._btn_monitor.clicked.connect(self._toggle_monitor)
        layout.addWidget(self._btn_monitor)

        # -- Auto inputs (timed repeaters) ----------------------------------
        layout.addWidget(QLabel("<b>Auto inputs (timed)</b>"))
        self._auto_list = QListWidget()
        layout.addWidget(self._auto_list, 1)

        auto_btns = QHBoxLayout()
        a_add = QPushButton("Add")
        a_edit = QPushButton("Edit")
        a_remove = QPushButton("Remove")
        a_add.clicked.connect(self._add_auto)
        a_edit.clicked.connect(self._edit_auto)
        a_remove.clicked.connect(self._remove_auto)
        for b in (a_add, a_edit, a_remove):
            auto_btns.addWidget(b)
        layout.addLayout(auto_btns)

        self._btn_auto = QPushButton("Start auto inputs")
        self._btn_auto.setCheckable(True)
        self._btn_auto.clicked.connect(self._toggle_autos)
        layout.addWidget(self._btn_auto)

        return panel

    def _build_menu(self) -> None:
        m = self.menuBar().addMenu("&Macro")
        m.addAction("New", self._new_macro)
        m.addAction("Open…", self._open_macro)
        m.addAction("Save As…", self._save_macro)
        t = self.menuBar().addMenu("&Watchers")
        t.addAction("Open…", self._open_triggers)
        t.addAction("Save As…", self._save_triggers)

    # -- recorder / player --------------------------------------------------
    def _toggle_record(self, from_button: bool = False) -> None:
        if self._recorder and self._recorder.running:
            # Trim the edge clicks that landed on the app's own Record/Stop
            # buttons so replays never click on MacroEngine itself.
            macro = self._recorder.stop(
                trim_leading_click=self._record_started_from_button,
                trim_trailing_click=from_button,
            )
            self._recorder = None
            macro.loop_count = self._loop.value()
            self._bridge.recorded.emit(macro)
            self._btn_record.setText(f"Record ({DEFAULT_RECORD})")
            self._set_status(f"Recorded {len(macro.events)} events")
            return
        if self._player.running:
            return
        self._record_started_from_button = from_button
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
        # TODO(audit): Esc is a *global* hotkey, so pressing Esc to cancel the
        # RegionSelector/PointPicker overlays also lands here (harmless today —
        # just a "Stopped" status). Consider pausing the panic hotkey while an
        # overlay is open, or choosing a rarer default like Ctrl+Alt+Q.
        self._player.stop()
        if self._monitor and self._monitor.running:
            self._monitor.stop()
            self._btn_monitor.setChecked(False)
            self._btn_monitor.setText("Start monitoring")
        if self._auto_runner and self._auto_runner.running:
            self._auto_runner.stop()
            self._auto_runner = None
            self._btn_auto.setChecked(False)
            self._btn_auto.setText("Start auto inputs")
        self._set_status("Stopped")

    # -- triggers & buff groups ---------------------------------------------
    def _refresh_triggers(self) -> None:
        # List triggers first, then buff groups. self._rows keeps the row->object
        # mapping so Edit/Remove can dispatch to the right dialog.
        self._trigger_list.clear()
        self._rows: List[tuple] = []
        for t in self._triggers:
            self._trigger_list.addItem(
                QListWidgetItem(f"{'●' if t.enabled else '○'} [trigger] {t.name} — {t.describe()}")
            )
            self._rows.append(("trigger", t))
        for g in self._groups:
            self._trigger_list.addItem(
                QListWidgetItem(f"{'●' if g.enabled else '○'} [buffs] {g.describe()}")
            )
            self._rows.append(("group", g))

    def _add_trigger(self) -> None:
        dlg = TriggerDialog(parent=self)
        if dlg.exec():
            self._triggers.append(dlg.get_trigger())
            self._refresh_triggers()

    def _add_group(self) -> None:
        dlg = BuffGroupDialog(parent=self)
        if dlg.exec():
            self._groups.append(dlg.get_group())
            self._refresh_triggers()

    def _edit_selected(self) -> None:
        row = self._trigger_list.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        kind, obj = self._rows[row]
        if kind == "trigger":
            dlg = TriggerDialog(trigger=obj, parent=self)
            if dlg.exec():
                self._triggers[self._triggers.index(obj)] = dlg.get_trigger()
        else:
            dlg = BuffGroupDialog(group=obj, parent=self)
            if dlg.exec():
                self._groups[self._groups.index(obj)] = dlg.get_group()
        self._refresh_triggers()

    def _remove_selected(self) -> None:
        row = self._trigger_list.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        kind, obj = self._rows[row]
        (self._triggers if kind == "trigger" else self._groups).remove(obj)
        self._refresh_triggers()

    def _toggle_monitor(self) -> None:
        if self._monitor and self._monitor.running:
            self._monitor.stop()
            self._monitor = None
            self._btn_monitor.setText("Start monitoring")
            self._set_status("Monitoring stopped")
            return
        if not self._triggers and not self._groups:
            self._btn_monitor.setChecked(False)
            self._set_status("Add a trigger or buff group before monitoring")
            return
        self._monitor = Monitor(
            self._triggers,
            groups=self._groups,
            on_fire=lambda label: self._bridge.trigger_fired.emit(label),
        )
        self._monitor.start()
        self._btn_monitor.setText("Stop monitoring")
        self._set_status("Monitoring…")

    def _on_trigger_fired(self, name: str) -> None:
        self._set_status(f"Fired: {name}")

    # -- auto inputs --------------------------------------------------------
    def _refresh_autos(self) -> None:
        self._auto_list.clear()
        for a in self._auto_inputs:
            self._auto_list.addItem(
                QListWidgetItem(f"{'●' if a.enabled else '○'} {a.describe()}")
            )

    def _add_auto(self) -> None:
        dlg = AutoInputDialog(parent=self)
        if dlg.exec():
            self._auto_inputs.append(dlg.get_auto())
            self._refresh_autos()

    def _edit_auto(self) -> None:
        row = self._auto_list.currentRow()
        if row < 0:
            return
        dlg = AutoInputDialog(auto=self._auto_inputs[row], parent=self)
        if dlg.exec():
            self._auto_inputs[row] = dlg.get_auto()
            self._refresh_autos()

    def _remove_auto(self) -> None:
        row = self._auto_list.currentRow()
        if row >= 0:
            del self._auto_inputs[row]
            self._refresh_autos()

    def _toggle_autos(self) -> None:
        if self._auto_runner and self._auto_runner.running:
            self._auto_runner.stop()
            self._auto_runner = None
            self._btn_auto.setText("Start auto inputs")
            self._set_status("Auto inputs stopped")
            return
        if not self._auto_inputs:
            self._btn_auto.setChecked(False)
            self._set_status("Add an auto input first")
            return
        self._auto_runner = AutoRunner(
            self._auto_inputs,
            on_fire=lambda name: self._bridge.trigger_fired.emit(name),
        )
        self._auto_runner.start()
        self._btn_auto.setText("Stop auto inputs")
        self._set_status("Auto inputs running…")

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
            self, "Open watchers", "", "Watcher files (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            self._triggers, self._groups, self._auto_inputs = load_watchers(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self._refresh_triggers()
        self._refresh_autos()
        self._set_status(f"Opened {path}")

    def _save_triggers(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save watchers", "watchers.json", "Watcher files (*.json)"
        )
        if not path:
            return
        try:
            save_watchers(self._triggers, self._groups, path, self._auto_inputs)
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
        if self._auto_runner and self._auto_runner.running:
            self._auto_runner.stop()
        if self._recorder and self._recorder.running:
            self._recorder.stop()
        self._hotkeys.stop()
        super().closeEvent(event)
