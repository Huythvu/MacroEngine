"""Dialogs for buff groups: watch one region (a buff bar) for several buff icons.

``BuffItemDialog`` captures a single buff icon (by boxing it on screen) and shows a
thumbnail plus a live "Test" readout. ``BuffGroupDialog`` owns the shared region and
the list of buff items.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
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

from ..models import actions
from ..models.buff import BuffGroup, BuffItem
from ..models.trigger import COND_ABSENT, COND_PRESENT
from ..vision import capture, detector
from .action_widget import ActionWidget
from .imaging import pixmap_from_png
from .region_selector import RegionSelector
from .util import wrap


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

        # click-on-match is available because a buff item always has a template.
        self._action_widget = ActionWidget(
            allowed=actions.ALL_ACTIONS,
            action=self._item.action,
            key=self._item.action_key,
            text=self._item.action_text,
            x=self._item.action_x,
            y=self._item.action_y,
            button=self._item.action_button,
            macro_path=self._item.action_macro_path,
        )

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
        form.addRow("Reference:", wrap(cap_row))
        form.addRow("Condition:", self._condition)
        form.addRow("Match threshold:", self._threshold)
        form.addRow("Cooldown (s):", self._cooldown)
        form.addRow("Test:", wrap(test_row))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self._action_widget)
        root.addWidget(buttons)

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
        v = self._action_widget.values()
        it.action = v["action"]
        it.action_key = v["key"]
        it.action_text = v["text"]
        it.action_x, it.action_y, it.action_button = v["x"], v["y"], v["button"]
        it.action_macro_path = v["macro_path"]
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
        form.addRow("Region:", wrap(region_row))

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

