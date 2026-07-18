"""A tiny always-on-top status overlay showing active states over the game.

Shows colored badges — REC / PLAY / MON / AUTO — in the top-right of the primary
screen; hidden when everything is idle. Click-through and never steals focus.

Note: like screen capture, this can't draw over a fullscreen-exclusive DirectX
game — use borderless/windowed mode. It sits top-right to stay out of watched
regions.
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

_BADGE_W = 52
_BADGE_H = 24
_GAP = 6
_MARGIN = 12


class StatusOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._badges: List[Tuple[str, QColor]] = []

    def set_states(self, recording=False, playing=False, monitoring=False, auto=False) -> None:
        badges: List[Tuple[str, QColor]] = []
        if recording:
            badges.append(("REC", QColor(230, 62, 62)))
        if playing:
            badges.append(("PLAY", QColor(46, 196, 138)))
        if monitoring:
            badges.append(("MON", QColor(80, 140, 255)))
        if auto:
            badges.append(("AUTO", QColor(240, 160, 40)))
        self._badges = badges
        if not badges:
            self.hide()
            return
        self._reposition()
        self.update()
        if not self.isVisible():
            self.show()

    def _reposition(self) -> None:
        n = len(self._badges)
        width = n * _BADGE_W + (n + 1) * _GAP
        height = _BADGE_H + 2 * _GAP
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.setGeometry(geo.right() - width - _MARGIN, geo.top() + _MARGIN, width, height)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont("Sans", 9, QFont.Bold))
        x = _GAP
        for label, color in self._badges:
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, _GAP, _BADGE_W, _BADGE_H, 6, 6)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(x, _GAP, _BADGE_W, _BADGE_H, Qt.AlignCenter, label)
            x += _BADGE_W + _GAP
