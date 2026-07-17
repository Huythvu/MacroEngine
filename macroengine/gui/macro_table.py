"""Editable timeline widget for a macro's events.

Delays are editable inline; structural changes (delete, reorder, insert taps and
clicks) are driven by the buttons alongside the table.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..models.event import KEY_DOWN, KEY_UP, MOUSE_CLICK, Event
from ..models.macro import Macro

_COLUMNS = ["#", "Type", "Details", "Delay (s)"]


class MacroTableModel(QAbstractTableModel):
    def __init__(self, macro: Optional[Macro] = None) -> None:
        super().__init__()
        self._events: List[Event] = macro.events if macro else []

    def set_events(self, events: List[Event]) -> None:
        self.beginResetModel()
        self._events = events
        self.endResetModel()

    @property
    def events(self) -> List[Event]:
        return self._events

    # -- Qt model interface -------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._events)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        ev = self._events[index.row()]
        col = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == 0:
                return index.row() + 1
            if col == 1:
                return ev.type
            if col == 2:
                return ev.describe()
            if col == 3:
                return f"{ev.delay:.3f}" if role == Qt.DisplayRole else ev.delay
        return None

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 3:  # delay is editable
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index, value, role=Qt.EditRole) -> bool:
        if role != Qt.EditRole or index.column() != 3:
            return False
        try:
            delay = max(0.0, float(value))
        except (TypeError, ValueError):
            return False
        self._events[index.row()].delay = delay
        self.dataChanged.emit(index, index, [Qt.DisplayRole])
        return True

    # -- structural edits ---------------------------------------------------
    def delete_rows(self, rows: List[int]) -> None:
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < len(self._events):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._events[row]
                self.endRemoveRows()

    def move_row(self, row: int, delta: int) -> int:
        target = row + delta
        if not (0 <= row < len(self._events)) or not (0 <= target < len(self._events)):
            return row
        self.beginResetModel()
        self._events[row], self._events[target] = self._events[target], self._events[row]
        self.endResetModel()
        return target

    def insert_events(self, at: int, events: List[Event]) -> None:
        at = max(0, min(at, len(self._events)))
        self.beginInsertRows(QModelIndex(), at, at + len(events) - 1)
        self._events[at:at] = events
        self.endInsertRows()


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
        btn_click = QPushButton("Add Click…")
        btn_delete.clicked.connect(self._delete)
        btn_up.clicked.connect(lambda: self._move(-1))
        btn_down.clicked.connect(lambda: self._move(1))
        btn_key.clicked.connect(self._add_key)
        btn_click.clicked.connect(self._add_click)

        buttons = QHBoxLayout()
        for b in (btn_delete, btn_up, btn_down, btn_key, btn_click):
            buttons.addWidget(b)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(buttons)

    def _selected_rows(self) -> List[int]:
        return sorted({i.row() for i in self._table.selectionModel().selectedRows()})

    def _current_row(self) -> int:
        rows = self._selected_rows()
        return rows[0] if rows else self._model.rowCount()

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
        text, ok = QInputDialog.getText(
            self, "Add Click", "x,y (screen coordinates):"
        )
        if not ok or "," not in text:
            return
        try:
            xs, ys = text.split(",", 1)
            x, y = int(xs.strip()), int(ys.strip())
        except ValueError:
            return
        at = self._current_row()
        self._model.insert_events(
            at,
            [
                Event(type=MOUSE_CLICK, delay=0.05, data={"x": x, "y": y, "button": "left", "pressed": True}),
                Event(type=MOUSE_CLICK, delay=0.05, data={"x": x, "y": y, "button": "left", "pressed": False}),
            ],
        )
