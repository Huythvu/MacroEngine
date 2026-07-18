"""MacroEngine main window: recorder controls, editable timeline, and the
vision-triggers panel.

Recorder/player/monitor callbacks arrive on non-GUI threads (pynput / worker
threads). They are marshaled back onto the GUI thread via the :class:`_Bridge`
QObject signals, which Qt delivers as queued connections.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import event_names_for, load_settings, save_settings
from ..core.hotkeys import HotkeyManager
from ..core.autorunner import AutoRunner
from ..core.player import Player
from ..core.recorder import Recorder
from ..models.autoinput import AutoInput
from ..models.buff import BuffGroup
from ..models.macro import Macro
from ..models.store import load_watchers, save_watchers
from ..models.trigger import Trigger
from ..paths import macros_dir, safe_filename, watchers_file
from ..resources import app_icon_path
from ..vision.monitor import Monitor
from .auto_input_dialog import AutoInputDialog
from .buff_group_dialog import BuffGroupDialog
from .editable_list import EditableListPanel
from .flow_layout import FlowLayout
from .library_panel import LibraryPanel
from .log_panel import LogPanel
from .macro_table import MacroTableModel, MacroTableView
from .routine_panel import RoutinePanel
from .trigger_dialog import TriggerDialog


def _fmt(spec: str) -> str:
    """'<f9>' -> 'F9' for button labels."""
    return spec.strip().strip('<>').upper()


class _Bridge(QObject):
    recorded = Signal(object)          # Macro
    playback_finished = Signal()
    trigger_fired = Signal(str)
    log_line = Signal(str)
    hotkey_record = Signal()
    hotkey_play = Signal()
    hotkey_panic = Signal()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MacroEngine")
        self.resize(900, 640)
        self.setMinimumSize(380, 320)
        icon_path = app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self._settings = load_settings()
        self._macro = Macro()
        self._model = MacroTableModel(self._macro)
        self._triggers: List[Trigger] = []
        self._groups: List[BuffGroup] = []
        self._rows: List[tuple] = []
        self._auto_inputs: List[AutoInput] = []
        self._auto_runner: Optional[AutoRunner] = None
        self._record_started_from_button = False
        self._cd_timer: Optional[QTimer] = None
        self._cd_done = None
        self._cd_button = None
        self._cd_base_label = None

        self._recorder: Optional[Recorder] = None
        self._player = Player(on_finished=lambda: self._bridge.playback_finished.emit())
        self._monitor: Optional[Monitor] = None

        self._bridge = _Bridge()
        self._bridge.recorded.connect(self._on_recorded)
        self._bridge.playback_finished.connect(self._on_playback_finished)
        self._bridge.trigger_fired.connect(self._on_trigger_fired)
        self._bridge.log_line.connect(self._append_log)
        self._bridge.hotkey_record.connect(self._toggle_record)
        self._bridge.hotkey_play.connect(self._toggle_play)
        self._bridge.hotkey_panic.connect(self._panic)

        self._build_ui()
        self._build_menu()
        self._restore_geometry()

        self._hotkeys: Optional[HotkeyManager] = None
        self._start_hotkeys()
        self._load_session()

        self._overlay = None
        self._apply_overlay_setting()
        self._overlay_timer = QTimer(self)
        self._overlay_timer.timeout.connect(self._update_overlay)
        self._overlay_timer.start(300)

        self._tray = None
        self._quitting = False
        self._build_tray()

        self._set_status("Ready")

    # -- settings / hotkeys -------------------------------------------------
    def _hotkey_specs(self):
        s = self._settings
        return (s["record_hotkey"], s["play_hotkey"], s["panic_hotkey"])

    def _start_hotkeys(self) -> None:
        if self._hotkeys is not None:
            self._hotkeys.stop()
        rec, play, panic = self._hotkey_specs()
        self._hotkeys = HotkeyManager(
            on_record=lambda: self._bridge.hotkey_record.emit(),
            on_play=lambda: self._bridge.hotkey_play.emit(),
            on_panic=lambda: self._bridge.hotkey_panic.emit(),
            record_key=rec, play_key=play, panic_key=panic,
        )
        self._hotkeys.start()
        # Keep button labels in sync with the bound keys.
        self._btn_record.setText(f"Record ({_fmt(rec)})")
        self._btn_play.setText(f"Play ({_fmt(play)})")
        self._btn_stop.setText(f"Stop ({_fmt(panic)})")

    def _apply_overlay_setting(self) -> None:
        from .overlay import StatusOverlay

        enabled = bool(self._settings["overlay_enabled"])
        if enabled and self._overlay is None:
            self._overlay = StatusOverlay()
        elif not enabled and self._overlay is not None:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        self._update_overlay()

    def _update_overlay(self) -> None:
        if self._overlay is None:
            return
        self._overlay.set_states(
            recording=bool(self._recorder and self._recorder.running),
            playing=self._player.running,
            monitoring=bool(self._monitor and self._monitor.running),
            auto=bool(self._auto_runner and self._auto_runner.running),
        )

    # -- system tray --------------------------------------------------------
    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self.windowIcon() or QIcon(), self)
        self._tray.setToolTip("MacroEngine")
        menu = QMenu()
        menu.addAction("Show / Hide", self._toggle_window)
        menu.addSeparator()
        menu.addAction("Start/stop monitoring", self._toggle_monitor)
        menu.addAction("Start/stop auto inputs", self._toggle_autos)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _quit(self) -> None:
        self._quitting = True
        self.close()

    def changeEvent(self, event) -> None:
        # Minimize to tray instead of the taskbar (when a tray is available).
        if (
            event.type() == QEvent.WindowStateChange
            and self.isMinimized()
            and self._tray is not None
        ):
            QTimer.singleShot(0, self.hide)
        super().changeEvent(event)

    def _restore_geometry(self) -> None:
        win = self._settings.get("window")
        if isinstance(win, list) and len(win) == 4:
            try:
                self.setGeometry(int(win[0]), int(win[1]), int(win[2]), int(win[3]))
            except Exception:  # noqa: BLE001
                pass

    def _load_session(self) -> None:
        """Restore triggers, buff groups and auto inputs from the last session."""
        path = watchers_file()
        if not path.exists():
            return
        try:
            self._triggers, self._groups, self._auto_inputs = load_watchers(path)
        except Exception:  # noqa: BLE001
            return
        self._refresh_triggers()
        self._refresh_autos()

    def _save_session(self) -> None:
        try:
            save_watchers(self._triggers, self._groups, watchers_file(), self._auto_inputs)
        except Exception:  # noqa: BLE001
            pass

    # -- UI construction ----------------------------------------------------
    def _build_ui(self) -> None:
        # Recorder controls.
        self._btn_record = QPushButton("Record")
        self._btn_play = QPushButton("Play")
        self._btn_stop = QPushButton("Stop")
        self._btn_record.clicked.connect(lambda: self._toggle_record(from_button=True))
        self._btn_play.clicked.connect(lambda: self._toggle_play(from_button=True))
        self._btn_stop.clicked.connect(self._panic)

        self._loop = QSpinBox()
        self._loop.setRange(0, 99999)
        self._loop.setValue(1)
        self._loop.setToolTip("Number of loops (0 = repeat forever until Stop)")

        self._record_moves = QCheckBox("Mouse moves")
        self._record_moves.setToolTip("Record mouse movement (off = keyboard-only macros stay clean)")
        self._record_moves.setChecked(self._settings["record_mouse_moves"])

        loops_label = QLabel("Loops:")
        controls = FlowLayout(spacing=4)
        for w in (self._btn_record, self._btn_play, self._btn_stop,
                  loops_label, self._loop, self._record_moves):
            controls.addWidget(w)

        # Macro timeline.
        self._table = MacroTableView(self._model)

        recorder_body = QWidget()
        rb_layout = QVBoxLayout(recorder_body)
        rb_layout.setContentsMargins(0, 0, 0, 0)
        rb_layout.addLayout(controls)
        rb_layout.addWidget(self._table)

        recorder_split = QSplitter(Qt.Horizontal)
        recorder_split.addWidget(self._build_macro_library())
        recorder_split.addWidget(recorder_body)
        recorder_split.setStretchFactor(0, 1)
        recorder_split.setStretchFactor(1, 3)
        recorder_split.setCollapsible(0, True)  # drag the library shut for a narrow window

        recorder_tab = QWidget()
        recorder_layout = QVBoxLayout(recorder_tab)
        recorder_layout.addWidget(recorder_split)

        # Routine composer tab (chains saved macros with waits + vision checks).
        self._routine_panel = RoutinePanel(status_cb=self._set_status)

        # Watchers & auto inputs tab.
        watchers_tab = self._build_triggers_panel()

        tabs = QTabWidget()
        i_rec = tabs.addTab(recorder_tab, "Recorder")
        i_rou = tabs.addTab(self._routine_panel, "Routine")
        i_wat = tabs.addTab(watchers_tab, "Watchers && Auto")
        tabs.setTabToolTip(i_rec, "Record and play back a single macro (keyboard + mouse).")
        tabs.setTabToolTip(
            i_rou,
            "Chain small saved macros with waits and 'wait until the screen shows X' "
            "steps — great for dailies. Pick a saved routine on the left, or build one.",
        )
        tabs.setTabToolTip(
            i_wat,
            "React to the screen automatically: vision triggers & buff groups fire a "
            "key when something appears/disappears; auto inputs repeat a key on a timer.",
        )
        self.setCentralWidget(tabs)

        # Activity log dock (visible across all tabs).
        self._log = LogPanel()
        dock = QDockWidget("Activity log", self)
        dock.setWidget(self._log)
        dock.setObjectName("activity_log")
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    def _append_log(self, text: str) -> None:
        self._log.append_line(text)

    def _build_macro_library(self) -> QWidget:
        self._macro_library = LibraryPanel(
            "Saved macros",
            directory=macros_dir,
            name_of=lambda p: Macro.load(p).name,
            on_open=self._macro_open_path,
            on_run=self._macro_run_path,
            extra_actions=[("Save…", self._macro_lib_save)],
        )
        return self._macro_library

    def _macro_open_path(self, path: Path) -> None:
        try:
            self._macro = Macro.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self._model.set_events(self._macro.events)
        self._loop.setValue(self._macro.loop_count)
        self._set_status(f"Opened macro '{self._macro.name}'")

    def _macro_run_path(self, path: Path) -> None:
        self._macro_open_path(path)
        self._toggle_play()

    def _macro_lib_save(self) -> None:
        if not self._macro.events:
            self._set_status("Nothing to save — record or open a macro first")
            return
        default = self._macro.name if self._macro.name not in ("", "Recorded") else ""
        name, ok = QInputDialog.getText(self, "Save macro", "Name:", text=default)
        if not ok or not name.strip():
            return
        self._macro.name = name.strip()
        self._macro.loop_count = self._loop.value()
        try:
            self._macro.save(macros_dir() / f"{safe_filename(self._macro.name)}.json")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._macro_library.refresh()
        self._set_status(f"Saved macro '{self._macro.name}' to library")

    def _build_triggers_panel(self) -> QWidget:
        # -- Left: vision triggers & buff groups ----------------------------
        watchers = QWidget()
        w_layout = QVBoxLayout(watchers)
        w_layout.setContentsMargins(0, 0, 0, 0)
        w_layout.addWidget(QLabel("<b>Vision triggers &amp; buff groups</b>"))

        self._trigger_list = QListWidget()
        self._trigger_list.setMinimumWidth(120)
        self._trigger_list.itemChanged.connect(self._watcher_check_changed)
        w_layout.addWidget(self._trigger_list, 1)

        btns = FlowLayout(spacing=4)
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
        w_layout.addLayout(btns)

        self._btn_monitor = QPushButton("Start monitoring")
        self._btn_monitor.setCheckable(True)
        self._btn_monitor.clicked.connect(self._toggle_monitor)
        w_layout.addWidget(self._btn_monitor)

        # -- Right: auto inputs (timed repeaters) ---------------------------
        autos = QWidget()
        a_layout = QVBoxLayout(autos)
        a_layout.setContentsMargins(0, 0, 0, 0)
        a_layout.addWidget(QLabel("<b>Auto inputs (timed)</b>"))
        self._auto_panel = EditableListPanel(
            self._auto_inputs,
            describe=lambda a: a.describe(),
            add_buttons=[("Add", self._make_auto)],
            on_edit=self._edit_auto_item,
            on_changed=self._save_session,
            reorderable=False,
        )
        a_layout.addWidget(self._auto_panel, 1)

        self._btn_auto = QPushButton("Start auto inputs")
        self._btn_auto.setCheckable(True)
        self._btn_auto.clicked.connect(self._toggle_autos)
        a_layout.addWidget(self._btn_auto)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(watchers)
        split.addWidget(autos)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        return split

    def _build_menu(self) -> None:
        m = self.menuBar().addMenu("&Macro")
        m.addAction("New", self._new_macro)
        m.addAction("Open…", self._open_macro)
        m.addAction("Save As…", self._save_macro)
        r = self.menuBar().addMenu("&Routine")
        r.addAction("New", self._routine_panel.new_routine)
        r.addAction("Open…", self._routine_panel.open_routine)
        r.addAction("Save As…", self._routine_panel.save_routine)
        t = self.menuBar().addMenu("&Watchers")
        t.addAction("Import…", self._open_triggers)
        t.addAction("Export…", self._save_triggers)
        o = self.menuBar().addMenu("&Options")
        o.addAction("Settings…", self._open_settings)

    def _open_settings(self) -> None:
        from .settings_dialog import SettingsDialog

        dlg = SettingsDialog(self._settings, parent=self)
        if not dlg.exec():
            return
        dlg.apply_to(self._settings)
        save_settings(self._settings)
        self._start_hotkeys()  # rebind live
        self._apply_overlay_setting()
        self._set_status("Settings updated")

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
            self._btn_record.setText(f"Record ({_fmt(self._settings['record_hotkey'])})")
            self._set_status(f"Recorded {len(macro.events)} events")
            return
        if self._counting_down:
            self._cancel_countdown()
            self._set_status("Countdown cancelled")
            return
        if self._player.running:
            return
        cd = int(self._settings["countdown_s"])
        if from_button and cd > 0:
            self._start_countdown(cd, lambda: self._begin_record(from_button), self._btn_record)
            return
        self._begin_record(from_button)

    def _begin_record(self, from_button: bool) -> None:
        self._record_started_from_button = from_button
        self._recorder = Recorder(
            record_mouse_move=self._record_moves.isChecked(),
            ignored_keys=event_names_for(*self._hotkey_specs()),
        )
        self._recorder.start()
        self._btn_record.setText("Stop recording")
        self._set_status("Recording… press again to stop")

    def _on_recorded(self, macro: Macro) -> None:
        self._macro = macro
        self._model.set_events(self._macro.events)

    def _toggle_play(self, from_button: bool = False) -> None:
        if self._player.running:
            self._panic()
            return
        if self._counting_down:
            self._cancel_countdown()
            self._set_status("Countdown cancelled")
            return
        if self._recorder and self._recorder.running:
            return
        if not self._macro.events:
            self._set_status("Nothing to play — record or open a macro first")
            return
        cd = int(self._settings["countdown_s"])
        if from_button and cd > 0:
            self._start_countdown(cd, self._begin_play, self._btn_play)
            return
        self._begin_play()

    def _begin_play(self) -> None:
        self._macro.loop_count = self._loop.value()
        self._btn_play.setText("Stop playing")
        self._set_status("Playing…")
        self._player.play(self._macro)

    # -- countdown ----------------------------------------------------------
    @property
    def _counting_down(self) -> bool:
        return self._cd_timer is not None

    def _start_countdown(self, seconds: int, on_done, button) -> None:
        self._cancel_countdown()
        self._cd_remaining = seconds
        self._cd_button = button
        self._cd_base_label = button.text()
        self._cd_done = on_done
        self._cd_timer = QTimer(self)
        self._cd_timer.timeout.connect(self._countdown_tick)
        button.setText(f"Starting in {seconds}…")
        self._set_status(f"Starting in {seconds}s… (click again or Stop to cancel)")
        self._cd_timer.start(1000)

    def _countdown_tick(self) -> None:
        self._cd_remaining -= 1
        if self._cd_remaining <= 0:
            self._cancel_countdown(run=True)
        elif self._cd_button is not None:
            self._cd_button.setText(f"Starting in {self._cd_remaining}…")

    def _cancel_countdown(self, run: bool = False) -> None:
        if self._cd_timer is not None:
            self._cd_timer.stop()
            self._cd_timer = None
        done, button, base = self._cd_done, self._cd_button, self._cd_base_label
        self._cd_done = self._cd_button = self._cd_base_label = None
        if button is not None and not run:
            button.setText(base)
        if run and done is not None:
            done()

    def _on_playback_finished(self) -> None:
        self._btn_play.setText(f"Play ({_fmt(self._settings['play_hotkey'])})")
        self._set_status("Playback finished")

    def _panic(self) -> None:
        # TODO(audit): Esc is a *global* hotkey, so pressing Esc to cancel the
        # RegionSelector/PointPicker overlays also lands here (harmless today —
        # just a "Stopped" status). Consider pausing the panic hotkey while an
        # overlay is open, or choosing a rarer default like Ctrl+Alt+Q.
        if self._counting_down:
            self._cancel_countdown()
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
        if self._routine_panel.running:
            self._routine_panel.stop()
        self._set_status("Stopped")

    # -- triggers & buff groups ---------------------------------------------
    def _refresh_triggers(self) -> None:
        # List triggers first, then buff groups. self._rows keeps the row->object
        # mapping so Edit/Remove can dispatch to the right dialog. Rows are
        # checkable: the checkbox is the item's enabled flag, and the runners
        # re-check it every tick, so toggling takes effect live.
        self._trigger_list.blockSignals(True)
        self._trigger_list.clear()
        self._rows: List[tuple] = []
        for t in self._triggers:
            self._add_checkable(self._trigger_list, f"[trigger] {t.name} — {t.describe()}", t.enabled)
            self._rows.append(("trigger", t))
        for g in self._groups:
            self._add_checkable(self._trigger_list, f"[buffs] {g.describe()}", g.enabled)
            self._rows.append(("group", g))
        self._trigger_list.blockSignals(False)

    @staticmethod
    def _add_checkable(list_widget: QListWidget, text: str, enabled: bool) -> None:
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        list_widget.addItem(item)

    def _watcher_check_changed(self, item: QListWidgetItem) -> None:
        row = self._trigger_list.row(item)
        if 0 <= row < len(self._rows):
            self._rows[row][1].enabled = item.checkState() == Qt.Checked

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
            on_log=lambda msg: self._bridge.log_line.emit(msg),
        )
        self._monitor.start()
        self._btn_monitor.setText("Stop monitoring")
        self._set_status("Monitoring…")

    def _on_trigger_fired(self, name: str) -> None:
        self._set_status(f"Fired: {name}")

    # -- auto inputs --------------------------------------------------------
    def _refresh_autos(self) -> None:
        self._auto_panel.set_items(self._auto_inputs)

    def _make_auto(self):
        dlg = AutoInputDialog(parent=self)
        return dlg.get_auto() if dlg.exec() else None

    def _edit_auto_item(self, auto):
        dlg = AutoInputDialog(auto=auto, parent=self)
        return dlg.get_auto() if dlg.exec() else None

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
            self, "Open macro", str(macros_dir()), "Macro files (*.json);;All files (*)"
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
            self, "Save macro", str(macros_dir() / "macro.json"), "Macro files (*.json)"
        )
        if not path:
            return
        self._macro.loop_count = self._loop.value()
        try:
            self._macro.save(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._macro_library.refresh()
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
        if hasattr(self, "_log"):
            self._log.append_line(text)

    def closeEvent(self, event) -> None:
        self._player.stop()
        if self._monitor and self._monitor.running:
            self._monitor.stop()
        if self._auto_runner and self._auto_runner.running:
            self._auto_runner.stop()
        if self._routine_panel.running:
            self._routine_panel.stop()
        if self._recorder and self._recorder.running:
            self._recorder.stop()
        self._save_session()
        self._save_settings_now()
        if self._hotkeys is not None:
            self._hotkeys.stop()
        if self._overlay is not None:
            self._overlay.hide()
        if self._tray is not None:
            self._tray.hide()
        super().closeEvent(event)

    def _save_settings_now(self) -> None:
        geo = self.geometry()
        self._settings["window"] = [geo.x(), geo.y(), geo.width(), geo.height()]
        self._settings["record_mouse_moves"] = self._record_moves.isChecked()
        save_settings(self._settings)
