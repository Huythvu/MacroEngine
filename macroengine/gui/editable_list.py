"""A reusable checkable list with Add / Edit / Remove and drag-to-reorder.

Drives the routine-steps list, the buff-items list, and the auto-inputs list —
each previously hand-rolled the same plumbing. Operates on a live ``items`` list
(mutated in place); every item is expected to have an ``enabled`` attribute, which
the row checkbox toggles. Reordering is drag-and-drop (Qt InternalMove), mirrored
back into the backing list.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .flow_layout import FlowLayout

# (label, factory) — factory() returns a new item, or None if cancelled.
AddButton = Tuple[str, Callable[[], object]]


class EditableListPanel(QWidget):
    def __init__(
        self,
        items: List,
        describe: Callable[[object], str],
        add_buttons: List[AddButton],
        on_edit: Callable[[object], Optional[object]],
        on_changed: Optional[Callable[[], None]] = None,
        reorderable: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._describe = describe
        self._on_edit = on_edit
        self._on_changed = on_changed

        self._list = QListWidget()
        self._list.setMinimumWidth(120)
        self._list.itemChanged.connect(self._check_changed)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context_menu)
        self._list.itemDoubleClicked.connect(lambda _i: self._edit())
        if reorderable:
            # Reorder by dragging rows; mirror the move into the backing list.
            self._list.setDragDropMode(QAbstractItemView.InternalMove)
            self._list.setDefaultDropAction(Qt.MoveAction)
            self._list.setDragDropOverwriteMode(False)
            self._list.model().rowsMoved.connect(self._rows_moved)
            self._list.setToolTip("Drag rows to reorder")

        buttons = FlowLayout(spacing=4)
        for label, factory in add_buttons:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, f=factory: self._add(f))
            buttons.addWidget(btn)
        btn_edit = QPushButton("Edit…")
        btn_remove = QPushButton("Remove")
        btn_edit.clicked.connect(self._edit)
        btn_remove.clicked.connect(self._remove)
        buttons.addWidget(btn_edit)
        buttons.addWidget(btn_remove)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list, 1)
        layout.addLayout(buttons)
        self.refresh()

    # -- API -----------------------------------------------------------------
    def refresh(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for item in self._items:
            row = QListWidgetItem(self._describe(item))
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(Qt.Checked if getattr(item, "enabled", True) else Qt.Unchecked)
            self._list.addItem(row)
        self._list.blockSignals(False)

    def current_row(self) -> int:
        return self._list.currentRow()

    def set_items(self, items: List) -> None:
        """Point the panel at a new list (e.g. after loading a routine)."""
        self._items = items
        self.refresh()

    def highlight(self, row: int) -> None:
        if 0 <= row < self._list.count():
            self._list.setCurrentRow(row)

    # -- internals -----------------------------------------------------------
    def _changed(self) -> None:
        self.refresh()
        if self._on_changed is not None:
            self._on_changed()

    def _check_changed(self, row_item: QListWidgetItem) -> None:
        row = self._list.row(row_item)
        if 0 <= row < len(self._items):
            self._items[row].enabled = row_item.checkState() == Qt.Checked
            if self._on_changed is not None:
                self._on_changed()

    def _add(self, factory: Callable[[], Optional[object]]) -> None:
        item = factory()
        if item is not None:
            self._items.append(item)
            self._changed()

    def _edit(self) -> None:
        row = self._list.currentRow()
        if not (0 <= row < len(self._items)):
            return
        edited = self._on_edit(self._items[row])
        if edited is not None:
            self._items[row] = edited
            self._changed()
            self._list.setCurrentRow(row)

    def _remove(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._items):
            del self._items[row]
            self._changed()

    # -- context menu --------------------------------------------------------
    def _context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        self._list.setCurrentRow(self._list.row(item))
        menu = QMenu(self)
        menu.addAction("Edit…", self._edit)
        if hasattr(self._items[self._list.currentRow()], "name"):
            menu.addAction("Rename…", self._rename)
        menu.addAction("Duplicate", self._duplicate)
        menu.addSeparator()
        menu.addAction("Remove", self._remove)
        menu.exec(self._list.mapToGlobal(pos))

    def _rename(self) -> None:
        row = self._list.currentRow()
        if not (0 <= row < len(self._items)):
            return
        item = self._items[row]
        current = getattr(item, "name", "")
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=current)
        if not ok:
            return
        item.name = new_name.strip()
        self._changed()
        self._list.setCurrentRow(row)

    def _duplicate(self) -> None:
        row = self._list.currentRow()
        if not (0 <= row < len(self._items)):
            return
        original = self._items[row]
        # Prefer the model's own serialization for a clean deep copy.
        if hasattr(original, "to_dict") and hasattr(type(original), "from_dict"):
            clone = type(original).from_dict(original.to_dict())
        else:
            clone = copy.deepcopy(original)
        if hasattr(clone, "name") and clone.name:
            clone.name = f"{clone.name} copy"
        self._items.insert(row + 1, clone)
        self._changed()
        self._list.setCurrentRow(row + 1)

    def _rows_moved(self, _parent, start: int, end: int, _dest, dest_row: int) -> None:
        # Qt has already moved the QListWidget rows; replay the same move on the
        # backing list so model and view stay in lockstep.
        count = end - start + 1
        moved = self._items[start:start + count]
        del self._items[start:start + count]
        insert_at = dest_row if dest_row < start else dest_row - count
        insert_at = max(0, min(insert_at, len(self._items)))
        self._items[insert_at:insert_at] = moved
        if self._on_changed is not None:
            self._on_changed()
