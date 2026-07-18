"""A read-only, timestamped activity log shown in a dock at the bottom."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit


class LogPanel(QPlainTextEdit):
    def __init__(self, max_lines: int = 2000, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(max_lines)  # old lines drop off automatically
        self.setFont(QFont("Consolas", 9))

    def append_line(self, text: str) -> None:
        self.appendPlainText(f"{datetime.now():%H:%M:%S}  {text}")
