"""Dialogs for buff groups: watch one region (a buff bar) for several buff icons.

``BuffItemDialog`` captures a single buff icon (by boxing it on screen) and shows a
thumbnail plus a live "Test" readout. ``BuffGroupDialog`` owns the shared region and
the list of buff items.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models.buff import BuffGroup, BuffItem
from ..models.trigger import (
    ACTION_PRESS_KEY,
    ACTION_RUN_MACRO,
    COND_ABSENT,
    COND_PRESENT,
)
from ..vision import capture, detector
from .key_capture import KeyCaptureEdit
from .region_selector import RegionSelector


def pixmap_from_png(png: Optional[bytes], size: int = 48) -> QPixmap:
    pm = QPixmap()
    if png:
        pm.loadFromData(png, "PNG")
    if not pm.isNull():
        pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm


class BuffItemDialog(QDialog):
    """Configure one buff: its reference icon, condition, and action."""

    def __init__(
        self,
        group_region: Tuple[int, int, int, int],
        item: Optional[BuffItem] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Buff")
        self._group_region = group_region
        self._item = item or BuffItem()
        self._template_png = self._item.template_png

        self._name = QLineEdit(self._item.name)

        # Reference icon capture + thumbnail.
        self._thumb = QLabel()
        self._thumb.setFixedSize(52, 52)
        self._thumb.setAlignment(Qt.AlignCenter)
        self._refresh_thumb()
        btn_capture = QPushButton("Box the buff icon on screen…")
        btn_capture.clicked.connect(self._capture)
        cap_row = QHBoxLayout()
        cap_row.addWidget(self._thumb)
        cap_row.addWidget(btn_capture, 1)

        self._condition = QComboBox()
        self._condition.addItem("Absent → act (buff ran out)", COND_ABSENT)
        self._condition.addItem("Present → act (e.g. debuff appeared)", COND_PRESENT)
        self._condition.setCurrentIndex(0 if self._item.condition == COND_ABSENT else 1)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.0, 1.0)
        self._threshold.setSingleStep(0.05)
        self._threshold.setDecimals(2)
        self._threshold.setValue(self._item.match_threshold)

        self._action = QComboBox()
        self._action.addItem("Press key", ACTION_PRESS_KEY)
        self._action.addItem("Run macro", ACTION_RUN_MACRO)
        self._action.setCurrentIndex(0 if self._item.action == ACTION_PRESS_KEY else 1)
        self._action.currentIndexChanged.connect(self._sync)
        self._action_key = KeyCaptureEdit(self._item.action_key)
        self._action_macro = QLineEdit(self._item.action_macro_path)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_macro)
        macro_row = QHBoxLayout()
        macro_row.addWidget(self._action_macro, 1)
        macro_row.addWidget(btn_browse)
        self._macro_widget = QWidget()
        self._macro_widget.setLayout(macro_row)

        self._cooldown = QDoubleSpinBox()
        self._cooldown.setRange(0.0, 3600.0)
        self._cooldown.setSingleStep(0.1)
        self._cooldown.setDecimals(2)
        self._cooldown.setValue(self._item.cooldown_s)

        # Test readout.
        self._test_label = QLabel("—")
        btn_test = QPushButton("Test now")
        btn_test.clicked.connect(self._test)
        test_row = QHBoxLayout()
        test_row.addWidget(btn_test)
        test_row.addWidget(self._test_label, 1)

        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Reference:", _wrap(cap_row))
        form.addRow("Condition:", self._condition)
        form.addRow("Match threshold:", self._threshold)
        form.addRow("Action:", self._action)
        self._key_row_label = QLabel("Key:")
        form.addRow(self._key_row_label, self._action_key)
        self._macro_row_label = QLabel("Macro:")
        form.addRow(self._macro_row_label, self._macro_widget)
        form.addRow("Cooldown (s):", self._cooldown)
        form.addRow("Test:", _wrap(test_row))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)
        self._sync()

    # -- helpers ------------------------------------------------------------
    def _refresh_thumb(self) -> None:
        pm = pixmap_from_png(self._template_png, 50)
        if pm.isNull():
            self._thumb.setText("(none)")
        else:
            self._thumb.setPixmap(pm)

    def _capture(self) -> None:
        sel = RegionSelector(self)
        if not sel.exec() or not sel.region:
            return
        try:
            image = capture.grab_region(sel.region)
            self._template_png = detector.encode_png(image)
            self._refresh_thumb()
            self._test()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Capture failed", str(exc))

    def _browse_macro(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select macro", "", "Macro files (*.json);;All files (*)"
        )
        if path:
            self._action_macro.setText(path)

    def _sync(self) -> None:
        is_key = self._action.currentData() == ACTION_PRESS_KEY
        self._key_row_label.setVisible(is_key)
        self._action_key.setVisible(is_key)
        self._macro_row_label.setVisible(not is_key)
        self._macro_widget.setVisible(not is_key)

    def _test(self) -> None:
        if not self._template_png:
            self._test_label.setText("Capture a reference first")
            return
        try:
            image = capture.grab_region(self._group_region)
            present, score = detector.template_present(
                image, self._template_png, self._threshold.value()
            )
        except Exception as exc:  # noqa: BLE001
            self._test_label.setText(f"error: {exc}")
            return
        state = "DETECTED ✓" if present else "not found ✗"
        self._test_label.setText(f"{state}  (score {score:.2f})")

    def _accept(self) -> None:
        if not self._template_png:
            QMessageBox.warning(self, "Missing reference", "Box the buff icon first.")
            return
        self.accept()

    def get_item(self) -> BuffItem:
        it = self._item
        it.name = self._name.text() or "Buff"
        it.template_png = self._template_png
        it.match_threshold = float(self._threshold.value())
        it.condition = self._condition.currentData()
        it.action = self._action.currentData()
        it.action_key = self._action_key.keystroke() or "1"
        it.action_macro_path = self._action_macro.text()
        it.cooldown_s = float(self._cooldown.value())
        return it


class BuffGroupDialog(QDialog):
    def __init__(self, group: Optional[BuffGroup] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Buff Group")
        self._group = group or BuffGroup()
        self._region = tuple(self._group.region)
        self._items: List[BuffItem] = list(self._group.items)

        self._name = QLineEdit(self._group.name)

        self._region_label = QLabel(self._region_text())
        btn_region = QPushButton("Select buff-bar region…")
        btn_region.clicked.connect(self._select_region)
        region_row = QHBoxLayout()
        region_row.addWidget(self._region_label, 1)
        region_row.addWidget(btn_region)

        self._list = QListWidget()
        self._list.setIconSize(QSize(32, 32))
        self._list.itemChanged.connect(self._check_changed)
        self._refresh_list()

        btn_add = QPushButton("Add buff…")
        btn_edit = QPushButton("Edit…")
        btn_remove = QPushButton("Remove")
        btn_test = QPushButton("Test all")
        btn_add.clicked.connect(self._add)
        btn_edit.clicked.connect(self._edit)
        btn_remove.clicked.connect(self._remove)
        btn_test.clicked.connect(self._test_all)
        item_btns = QHBoxLayout()
        for b in (btn_add, btn_edit, btn_remove, btn_test):
            item_btns.addWidget(b)

        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Region:", _wrap(region_row))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(QLabel("Buffs (each icon is searched for anywhere in the region):"))
        root.addWidget(self._list, 1)
        root.addLayout(item_btns)
        root.addWidget(buttons)
        self.resize(460, 460)

    # -- helpers ------------------------------------------------------------
    def _region_text(self) -> str:
        x, y, w, h = self._region
        return f"x={x}, y={y}, w={w}, h={h}"

    def _select_region(self) -> None:
        sel = RegionSelector(self)
        if sel.exec() and sel.region:
            self._region = sel.region
            self._region_label.setText(self._region_text())

    def _refresh_list(self, detections: Optional[dict] = None) -> None:
        # Rows are checkable: the checkbox toggles the buff's enabled flag so a
        # single buff can be paused without removing it from the group.
        self._list.blockSignals(True)
        self._list.clear()
        for idx, it in enumerate(self._items):
            text = it.describe()
            if detections and idx in detections:
                present, score = detections[idx]
                text += f"   [{'DETECTED ✓' if present else 'not found ✗'} {score:.2f}]"
            row = QListWidgetItem(text)
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(Qt.Checked if it.enabled else Qt.Unchecked)
            pm = pixmap_from_png(it.template_png, 32)
            if not pm.isNull():
                row.setIcon(QIcon(pm))
            self._list.addItem(row)
        self._list.blockSignals(False)

    def _check_changed(self, row_item: QListWidgetItem) -> None:
        row = self._list.row(row_item)
        if 0 <= row < len(self._items):
            self._items[row].enabled = row_item.checkState() == Qt.Checked

    def _add(self) -> None:
        dlg = BuffItemDialog(self._region, parent=self)
        if dlg.exec():
            self._items.append(dlg.get_item())
            self._refresh_list()

    def _edit(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        dlg = BuffItemDialog(self._region, item=self._items[row], parent=self)
        if dlg.exec():
            self._items[row] = dlg.get_item()
            self._refresh_list()

    def _remove(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            del self._items[row]
            self._refresh_list()

    def _test_all(self) -> None:
        try:
            image = capture.grab_region(self._region)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Capture failed", str(exc))
            return
        detections = {}
        for idx, it in enumerate(self._items):
            present, score = detector.template_present(image, it.template_png, it.match_threshold)
            detections[idx] = (present, score)
        self._refresh_list(detections)

    def get_group(self) -> BuffGroup:
        g = self._group
        g.name = self._name.text() or "Buff group"
        g.region = self._region
        g.items = self._items
        return g


# TODO(audit): duplicated helper — see note in trigger_dialog.py (gui/util.py).
def _wrap(layout) -> QWidget:
    w = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    w.setLayout(layout)
    return w
