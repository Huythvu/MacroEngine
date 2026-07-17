"""A translucent fullscreen overlay for drag-selecting a screen region.

Usage::

    sel = RegionSelector()
    if sel.exec():
        x, y, w, h = sel.region
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QDialog


class RegionSelector(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.region: Optional[Tuple[int, int, int, int]] = None
        self._origin: Optional[QPoint] = None
        self._current: Optional[QPoint] = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setWindowOpacity(0.30)
        self.setCursor(Qt.CrossCursor)
        # Cover the whole virtual desktop (all monitors).
        vgeo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(vgeo)
        self._offset = vgeo.topLeft()

    # -- painting -----------------------------------------------------------
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 20, 20))
        if self._origin and self._current:
            rect = QRect(self._origin, self._current).normalized()
            painter.fillRect(rect, QColor(80, 140, 255))
            pen = QPen(QColor(255, 255, 255), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

    # -- mouse --------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        self._origin = event.position().toPoint()
        self._current = self._origin
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._origin is None:
            self.reject()
            return
        rect = QRect(self._origin, event.position().toPoint()).normalized()
        if rect.width() < 3 or rect.height() < 3:
            self.reject()
            return
        # Translate widget-local coords to global screen coords.
        gx = rect.x() + self._offset.x()
        gy = rect.y() + self._offset.y()
        self.region = (gx, gy, rect.width(), rect.height())
        self.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()
