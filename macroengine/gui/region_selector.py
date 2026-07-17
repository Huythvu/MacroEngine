"""Translucent fullscreen overlays for picking a screen region or a single point.

Usage::

    sel = RegionSelector()
    if sel.exec():
        x, y, w, h = sel.region

    pick = PointPicker()
    if pick.exec():
        x, y = pick.point
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QDialog

from ..screenmath import scale_point, scale_region


def _pixel_ratio(widget: QDialog) -> float:
    """Device pixel ratio of the screen the overlay is on (1.0 if unknown).

    Qt coordinates are logical pixels; mss/pynput use physical pixels, so
    everything this module returns must be scaled by this ratio (audit bug #1).
    """
    screen = widget.screen() or QGuiApplication.primaryScreen()
    return float(screen.devicePixelRatio()) if screen else 1.0


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
        # Translate widget-local coords to global screen coords, then convert
        # Qt logical pixels to physical pixels for mss/pynput.
        gx = rect.x() + self._offset.x()
        gy = rect.y() + self._offset.y()
        self.region = scale_region(
            (gx, gy, rect.width(), rect.height()), _pixel_ratio(self)
        )
        self.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()


class PointPicker(QDialog):
    """Fullscreen overlay that captures a single click and reports its global
    screen coordinates, so users never type raw pixel positions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.point: Optional[Tuple[int, int]] = None
        self.button: str = "left"

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setWindowOpacity(0.30)
        self.setCursor(Qt.CrossCursor)
        vgeo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(vgeo)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 20, 20))
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Sans", 16))
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "Click where the macro should click\n(right-click = right button, Esc = cancel)",
        )

    def mouseReleaseEvent(self, event) -> None:
        self.button = "right" if event.button() == Qt.RightButton else "left"
        gp = event.globalPosition().toPoint()
        # Qt logical pixels -> physical pixels (pynput clicks in physical).
        self.point = scale_point(gp.x(), gp.y(), _pixel_ratio(self))
        self.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()
