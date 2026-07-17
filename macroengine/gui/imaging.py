"""Shared image helpers for dialogs (PNG bytes -> QPixmap thumbnails)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


def pixmap_from_png(png: Optional[bytes], size: int = 48) -> QPixmap:
    """Decode PNG bytes into a QPixmap scaled to fit within ``size``x``size``
    (aspect preserved). Returns a null pixmap for empty/invalid input."""
    pm = QPixmap()
    if png:
        pm.loadFromData(png, "PNG")
    if not pm.isNull():
        pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm
