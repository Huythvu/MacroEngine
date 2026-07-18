"""A reusable checkable list with Add / Edit / Remove (and optional reordering).

Drives the routine-steps list, the buff-items list, and the auto-inputs list —
each previously hand-rolled the same plumbing. Operates on a live ``items`` list
(mutated in place); every item is expected to have an ``enabled`` attribute, which
the row checkbox toggles.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
        self._list.itemChanged.connect(self._check_changed)

        add_row = QHBoxLayout()
        for label, factory in add_buttons:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, f=factory: self._add(f))
            add_row.addWidget(btn)
        add_row.addStretch(1)

        edit_row = QHBoxLayout()
        btn_edit = QPushButton("Edit…")
        btn_remove = QPushButton("Remove")
        btn_edit.clicked.connect(self._edit)
        btn_remove.clicked.connect(self._remove)
        edit_row.addWidget(btn_edit)
        edit_row.addWidget(btn_remove)
        if reorderable:
            btn_up = QPushButton("Move Up")
            btn_down = QPushButton("Move Down")
            btn_up.clicked.connect(lambda: self._move(-1))
            btn_down.clicked.connect(lambda: self._move(1))
            edit_row.addWidget(btn_up)
            edit_row.addWidget(btn_down)
        edit_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list, 1)
        layout.addLayout(add_row)
        layout.addLayout(edit_row)
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

    def _move(self, delta: int) -> None:
        row = self._list.currentRow()
        target = row + delta
        if not (0 <= row < len(self._items)) or not (0 <= target < len(self._items)):
            return
        self._items[row], self._items[target] = self._items[target], self._items[row]
        self._changed()
        self._list.setCurrentRow(target)
