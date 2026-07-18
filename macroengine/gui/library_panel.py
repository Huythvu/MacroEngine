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
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LibraryPanel(QWidget):
    def __init__(
        self,
        title: str,
        directory: Callable[[], Path],
        name_of: Callable[[Path], str],
        on_open: Callable[[Path], None],
        on_run: Optional[Callable[[Path], None]] = None,
        extra_actions: Optional[List[Tuple[str, Callable[[], None]]]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._directory = directory
        self._name_of = name_of
        self._on_open = on_open
        self._on_run = on_run

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _i: self._open())
        layout.addWidget(self._list, 1)

        row1 = QHBoxLayout()
        btn_open = QPushButton("Open")
        btn_open.clicked.connect(self._open)
        row1.addWidget(btn_open)
        if on_run is not None:
            btn_run = QPushButton("Open & Run")
            btn_run.clicked.connect(self._run)
            row1.addWidget(btn_run)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        for label, cb in (extra_actions or []):
            btn = QPushButton(label)
            btn.clicked.connect(cb)
            row2.addWidget(btn)
        btn_delete = QPushButton("Delete")
        btn_refresh = QPushButton("Refresh")
        btn_delete.clicked.connect(self._delete)
        btn_refresh.clicked.connect(self.refresh)
        row2.addWidget(btn_delete)
        row2.addWidget(btn_refresh)
        layout.addLayout(row2)

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
