"""A reusable file-library list: shows saved ``*.json`` files from a folder with
Open / Open & Run / Delete / Refresh (and any extra buttons a caller supplies).

Used for both the saved-macros library and the saved-routines library so they
look and behave identically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .flow_layout import FlowLayout


class LibraryPanel(QWidget):
    def __init__(
        self,
        title: str,
        directory: Callable[[], Path],
        name_of: Callable[[Path], str],
        on_open: Callable[[Path], None],
        on_run: Optional[Callable[[Path], None]] = None,
        on_rename: Optional[Callable[[Path, str], Optional[Path]]] = None,
        on_duplicate: Optional[Callable[[Path], None]] = None,
        extra_actions: Optional[List[Tuple[str, Callable[[], None]]]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._directory = directory
        self._name_of = name_of
        self._on_open = on_open
        self._on_run = on_run
        self._on_rename = on_rename
        self._on_duplicate = on_duplicate

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        self._list = QListWidget()
        self._list.setMinimumWidth(120)
        # Clicking an item opens it right away — no separate Open step.
        self._list.itemClicked.connect(lambda _i: self._open())
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self._list, 1)

        buttons = FlowLayout(spacing=4)
        if on_run is not None:
            btn_run = QPushButton("Run")
            btn_run.setToolTip("Open the selected item and run it")
            btn_run.clicked.connect(self._run)
            buttons.addWidget(btn_run)
        for label, cb in (extra_actions or []):
            btn = QPushButton(label)
            btn.clicked.connect(cb)
            buttons.addWidget(btn)
        btn_delete = QPushButton("Delete")
        btn_refresh = QPushButton("Refresh")
        btn_delete.clicked.connect(self._delete)
        btn_refresh.clicked.connect(self.refresh)
        buttons.addWidget(btn_delete)
        buttons.addWidget(btn_refresh)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        for path in sorted(self._directory().glob("*.json")):
            try:
                name = self._name_of(path)
            except Exception:  # noqa: BLE001
                name = path.stem
            item = QListWidgetItem(name or path.stem)
            item.setData(Qt.UserRole, str(path))
            self._list.addItem(item)

    def selected_path(self) -> Optional[Path]:
        item = self._list.currentItem()
        return Path(item.data(Qt.UserRole)) if item else None

    # -- context menu --------------------------------------------------------
    def _context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        self._list.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Open", self._open)
        if self._on_run is not None:
            menu.addAction("Run", self._run)
        menu.addSeparator()
        if self._on_rename is not None:
            menu.addAction("Rename…", self._rename)
        if self._on_duplicate is not None:
            menu.addAction("Duplicate", self._duplicate)
        menu.addAction("Delete", self._delete)
        menu.exec(self._list.mapToGlobal(pos))

    def _rename(self) -> None:
        path = self.selected_path()
        if path is None or self._on_rename is None:
            return
        current = self._list.currentItem().text()
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=current)
        if not ok or not new_name.strip():
            return
        try:
            self._on_rename(path, new_name.strip())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Rename failed", str(exc))
            return
        self.refresh()

    def _duplicate(self) -> None:
        path = self.selected_path()
        if path is None or self._on_duplicate is None:
            return
        try:
            self._on_duplicate(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Duplicate failed", str(exc))
            return
        self.refresh()

    def _open(self) -> None:
        path = self.selected_path()
        if path is not None:
            self._on_open(path)

    def _run(self) -> None:
        path = self.selected_path()
        if path is not None and self._on_run is not None:
            self._on_run(path)

    def _delete(self) -> None:
        path = self.selected_path()
        if path is None:
            return
        if QMessageBox.question(
            self, "Delete", f"Delete '{path.stem}'?"
        ) != QMessageBox.Yes:
            return
        try:
            path.unlink()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Delete failed", str(exc))
            return
        self.refresh()
