"""Editable timeline widget for a macro's events.

Delays are editable inline; structural changes (delete, reorder, insert taps and
clicks) are driven by the buttons alongside the table.
"""

from __future__ import annotations

import json
from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QMimeData, QModelIndex, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..grouping import build_groups, group_describe, group_span_delay
from ..models.event import KEY_DOWN, KEY_UP, MOUSE_CLICK, Event
from ..models.macro import Macro
from .region_selector import PointPicker

_COLUMNS = ["#", "Type", "Details", "Delay (s)"]
# Clipboard format for pasting events back into the app (round-trips full data).
_EVENTS_MIME = "application/x-macroengine-events"


class MacroTableModel(QAbstractTableModel):
    """Renders the event list as *groups*. In compact mode, runs of same-kind
    events (held-key repeats, mouse-move streams) collapse to one row; the
    underlying events are never modified by grouping."""

    def __init__(self, macro: Optional[Macro] = None) -> None:
        super().__init__()
        self._events: List[Event] = macro.events if macro else []
        self._compact = True
        self._groups = build_groups(self._events, self._compact)

    def _rebuild(self) -> None:
        self._groups = build_groups(self._events, self._compact)

    def set_events(self, events: List[Event]) -> None:
        self.beginResetModel()
        self._events = events
        self._rebuild()
        self.endResetModel()

    def set_compact(self, compact: bool) -> None:
        self.beginResetModel()
        self._compact = compact
        self._rebuild()
        self.endResetModel()

    @property
    def compact(self) -> bool:
        return self._compact

    @property
    def events(self) -> List[Event]:
        return self._events

    # -- Qt model interface -------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._groups)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        start, length = self._groups[index.row()]
        ev = self._events[start]
        col = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == 0:
                return index.row() + 1
            if col == 1:
                return ("⊞ " if length > 1 else "") + ev.type
            if col == 2:
                return group_describe(self._events, start, length)
            if col == 3:
                total = ev.delay if length == 1 else group_span_delay(self._events, start, length)
                return f"{total:.3f}" if role == Qt.DisplayRole else total
        return None

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        # Delay is editable only for single-event rows (a group's delay is a total).
        if index.column() == 3 and self._groups[index.row()][1] == 1:
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index, value, role=Qt.EditRole) -> bool:
        if role != Qt.EditRole or index.column() != 3:
            return False
        start, length = self._groups[index.row()]
        if length != 1:
            return False
        try:
            delay = max(0.0, float(value))
        except (TypeError, ValueError):
            return False
        self._events[start].delay = delay
        self.dataChanged.emit(index, index, [Qt.DisplayRole])
        return True

    # -- structural edits (operate on whole display rows / spans) -----------
    def delete_rows(self, rows: List[int]) -> None:
        spans = [self._groups[r] for r in sorted(set(rows)) if 0 <= r < len(self._groups)]
        if not spans:
            return
        self.beginResetModel()
        for start, length in sorted(spans, reverse=True):
            del self._events[start:start + length]
        self._rebuild()
        self.endResetModel()

    def move_row(self, row: int, delta: int) -> int:
        target = row + delta
        if not (0 <= row < len(self._groups)) or not (0 <= target < len(self._groups)):
            return row
        a, b = (row, target) if row < target else (target, row)
        (sa, la), (sb, lb) = self._groups[a], self._groups[b]  # adjacent, so sb == sa + la
        self.beginResetModel()
        block_a = self._events[sa:sa + la]
        block_b = self._events[sb:sb + lb]
        self._events[sa:sb + lb] = block_b + block_a
        self._rebuild()
        self.endResetModel()
        return target

    def insert_events(self, at_row: int, events: List[Event]) -> None:
        if 0 <= at_row < len(self._groups):
            at = self._groups[at_row][0]
        else:
            at = len(self._events)
        self.beginResetModel()
        self._events[at:at] = events
        self._rebuild()
        self.endResetModel()

    def events_for_rows(self, rows: List[int]) -> List[Event]:
        """Underlying events for the given display rows (groups expanded)."""
        out: List[Event] = []
        for r in sorted(set(rows)):
            if 0 <= r < len(self._groups):
                start, length = self._groups[r]
                out.extend(self._events[start:start + length])
        return out


class MacroTableView(QWidget):
    def __init__(self, model: MacroTableModel, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._table = QTableView()
        self._table.setModel(model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setColumnWidth(2, 320)

        btn_delete = QPushButton("Delete")
        btn_up = QPushButton("Move Up")
        btn_down = QPushButton("Move Down")
        btn_key = QPushButton("Add Key Tap…")
        btn_click = QPushButton("Add Click (pick on screen)…")
        btn_copy = QPushButton("Copy")
        btn_paste = QPushButton("Paste")
        btn_delete.clicked.connect(self._delete)
        btn_up.clicked.connect(lambda: self._move(-1))
        btn_down.clicked.connect(lambda: self._move(1))
        btn_key.clicked.connect(self._add_key)
        btn_click.clicked.connect(self._add_click)
        btn_copy.clicked.connect(self._copy)
        btn_paste.clicked.connect(self._paste)
        btn_copy.setToolTip("Copy selected rows (Ctrl+C) — as text, and pasteable back in")
        btn_paste.setToolTip("Paste copied events (Ctrl+V)")

        # Standard clipboard shortcuts on the table.
        QShortcut(QKeySequence.Copy, self._table, activated=self._copy)
        QShortcut(QKeySequence.Paste, self._table, activated=self._paste)

        self._compact = QCheckBox("Compact view")
        self._compact.setChecked(model.compact)
        self._compact.setToolTip(
            "Collapse held keys and mouse-move streams into single rows "
            "(display only — playback is unchanged)."
        )
        self._compact.toggled.connect(model.set_compact)

        buttons = QHBoxLayout()
        for b in (btn_delete, btn_up, btn_down, btn_key, btn_click, btn_copy, btn_paste):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self._compact)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(buttons)

    def _selected_rows(self) -> List[int]:
        return sorted({i.row() for i in self._table.selectionModel().selectedRows()})

    def _current_row(self) -> int:
        rows = self._selected_rows()
        return rows[0] if rows else self._model.rowCount()

    def _copy(self) -> None:
        events = self._model.events_for_rows(self._selected_rows())
        if not events:
            return
        md = QMimeData()
        # App format: full round-trippable data for pasting back in.
        md.setData(_EVENTS_MIME, json.dumps([e.to_dict() for e in events]).encode("utf-8"))
        # Plain text: human-readable, for pasting into any editor.
        md.setText("\n".join(f"{e.describe()}\t{e.delay:.3f}s" for e in events))
        QGuiApplication.clipboard().setMimeData(md)

    def _paste(self) -> None:
        md = QGuiApplication.clipboard().mimeData()
        if not md.hasFormat(_EVENTS_MIME):
            return
        try:
            raw = json.loads(bytes(md.data(_EVENTS_MIME)).decode("utf-8"))
            events = [Event.from_dict(e) for e in raw]
        except Exception:
            return
        # Insert after the current selection (or at the end if nothing selected).
        rows = self._selected_rows()
        at = rows[-1] + 1 if rows else self._model.rowCount()
        self._model.insert_events(at, events)

    def _delete(self) -> None:
        self._model.delete_rows(self._selected_rows())

    def _move(self, delta: int) -> None:
        rows = self._selected_rows()
        if len(rows) != 1:
            return
        new_row = self._model.move_row(rows[0], delta)
        self._table.selectRow(new_row)

    def _add_key(self) -> None:
        key, ok = QInputDialog.getText(self, "Add Key Tap", "Key (e.g. a, 1, Key.enter):")
        if not ok or not key:
            return
        at = self._current_row()
        self._model.insert_events(
            at,
            [
                Event(type=KEY_DOWN, delay=0.05, data={"key": key}),
                Event(type=KEY_UP, delay=0.05, data={"key": key}),
            ],
        )

    def _add_click(self) -> None:
        # Pick the position by clicking on screen rather than typing coordinates.
        picker = PointPicker(self)
        if not picker.exec() or picker.point is None:
            return
        x, y = picker.point
        button = picker.button
        at = self._current_row()
        self._model.insert_events(
            at,
            [
                Event(type=MOUSE_CLICK, delay=0.05, data={"x": x, "y": y, "button": button, "pressed": True}),
                Event(type=MOUSE_CLICK, delay=0.05, data={"x": x, "y": y, "button": button, "pressed": False}),
            ],
        )
