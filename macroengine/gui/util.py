"""Small shared GUI helpers used across panels and dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


def wrap(layout) -> QWidget:
    """Wrap a layout in a margin-less QWidget (for QFormLayout rows etc.)."""
    w = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    w.setLayout(layout)
    return w


def labeled(text: str, widget: QWidget) -> QWidget:
    """A '<label> <widget>' row as a single widget."""
    row = QHBoxLayout()
    row.addWidget(QLabel(text))
    row.addWidget(widget, 1)
    return wrap(row)


def intro(text: str) -> QLabel:
    """A muted, wrapped one-line explainer shown at the top of a tab/panel."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: palette(mid); padding: 2px 0 6px 0;")
    return label
