"""Settings dialog: rebind the global hotkeys and tweak app options."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from ..config import HOTKEY_CHOICES


def _hotkey_combo(current: str) -> QComboBox:
    box = QComboBox()
    for choice in HOTKEY_CHOICES:
        box.addItem(choice.strip("<>").upper(), choice)
    idx = box.findData(current)
    if idx < 0:
        box.addItem(current.strip("<>").upper(), current)
        idx = box.count() - 1
    box.setCurrentIndex(idx)
    return box


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._settings = settings

        self._record = _hotkey_combo(settings["record_hotkey"])
        self._play = _hotkey_combo(settings["play_hotkey"])
        self._panic = _hotkey_combo(settings["panic_hotkey"])

        self._countdown = QSpinBox()
        self._countdown.setRange(0, 10)
        self._countdown.setValue(int(settings["countdown_s"]))
        self._countdown.setSuffix(" s")
        self._countdown.setSpecialValueText("off")
        self._countdown.setToolTip(
            "Countdown after clicking Record/Play (from a button) so you can switch "
            "to the game first. Hotkey starts stay instant."
        )

        self._overlay = QCheckBox("Show on-screen status overlay")
        self._overlay.setChecked(bool(settings["overlay_enabled"]))

        form = QFormLayout()
        form.addRow("Record hotkey:", self._record)
        form.addRow("Play hotkey:", self._play)
        form.addRow("Panic / stop hotkey:", self._panic)
        form.addRow("Start countdown:", self._countdown)
        form.addRow(self._overlay)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _accept(self) -> None:
        keys = [self._record.currentData(), self._play.currentData(), self._panic.currentData()]
        if len(set(keys)) != 3:
            QMessageBox.warning(
                self, "Duplicate hotkeys", "Record, Play and Panic must all differ."
            )
            return
        self.accept()

    def apply_to(self, settings: dict) -> None:
        settings["record_hotkey"] = self._record.currentData()
        settings["play_hotkey"] = self._play.currentData()
        settings["panic_hotkey"] = self._panic.currentData()
        settings["countdown_s"] = int(self._countdown.value())
        settings["overlay_enabled"] = self._overlay.isChecked()
