"""Dialog to create or edit a single vision :class:`Trigger`."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..models.trigger import (
    ACTION_PRESS_KEY,
    ACTION_RUN_MACRO,
    COND_ABSENT,
    COND_PRESENT,
    COND_RATIO_ABOVE,
    COND_RATIO_BELOW,
    DETECT_COLOR,
    DETECT_TEMPLATE,
    Trigger,
)
from ..vision import capture, detector
from .region_selector import RegionSelector


def _spin(minimum, maximum, value, step=1, decimals=None) -> QWidget:
    if decimals is None:
        box = QSpinBox()
    else:
        box = QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setSingleStep(step)
    box.setRange(minimum, maximum)
    box.setValue(value)
    return box


class TriggerDialog(QDialog):
    def __init__(self, trigger: Optional[Trigger] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vision Trigger")
        self._trigger = trigger or Trigger()

        self._name = QLineEdit(self._trigger.name)

        # Region.
        self._region = tuple(self._trigger.region)
        self._region_label = QLabel(self._region_text())
        btn_region = QPushButton("Select Region…")
        btn_region.clicked.connect(self._select_region)
        region_row = QHBoxLayout()
        region_row.addWidget(self._region_label, 1)
        region_row.addWidget(btn_region)

        # Detection kind.
        self._detection = QComboBox()
        self._detection.addItem("Template (image match)", DETECT_TEMPLATE)
        self._detection.addItem("Color (HSV ratio)", DETECT_COLOR)
        self._detection.setCurrentIndex(
            0 if self._trigger.detection == DETECT_TEMPLATE else 1
        )
        self._detection.currentIndexChanged.connect(self._sync_visibility)

        # Template group.
        self._template_png = self._trigger.template_png
        self._template_status = QLabel(self._template_text())
        btn_capture = QPushButton("Capture Snapshot from Region")
        btn_capture.clicked.connect(self._capture_template)
        self._match_threshold = _spin(0.0, 1.0, self._trigger.match_threshold, 0.05, 2)
        tpl_form = QFormLayout()
        tpl_form.addRow(self._template_status)
        tpl_form.addRow(btn_capture)
        tpl_form.addRow("Match threshold:", self._match_threshold)
        self._template_group = QGroupBox("Template settings")
        self._template_group.setLayout(tpl_form)

        # Color group.
        self._h_lo = _spin(0, 179, self._trigger.hsv_lower[0])
        self._s_lo = _spin(0, 255, self._trigger.hsv_lower[1])
        self._v_lo = _spin(0, 255, self._trigger.hsv_lower[2])
        self._h_hi = _spin(0, 179, self._trigger.hsv_upper[0])
        self._s_hi = _spin(0, 255, self._trigger.hsv_upper[1])
        self._v_hi = _spin(0, 255, self._trigger.hsv_upper[2])
        self._ratio_threshold = _spin(0.0, 1.0, self._trigger.ratio_threshold, 0.05, 2)
        lo_row = QHBoxLayout()
        for w in (self._h_lo, self._s_lo, self._v_lo):
            lo_row.addWidget(w)
        hi_row = QHBoxLayout()
        for w in (self._h_hi, self._s_hi, self._v_hi):
            hi_row.addWidget(w)
        color_form = QFormLayout()
        color_form.addRow("HSV lower (H,S,V):", _wrap(lo_row))
        color_form.addRow("HSV upper (H,S,V):", _wrap(hi_row))
        color_form.addRow("Ratio threshold:", self._ratio_threshold)
        self._color_group = QGroupBox("Color settings")
        self._color_group.setLayout(color_form)

        # Condition.
        self._condition = QComboBox()

        # Action.
        self._action = QComboBox()
        self._action.addItem("Press key", ACTION_PRESS_KEY)
        self._action.addItem("Run macro", ACTION_RUN_MACRO)
        self._action.setCurrentIndex(
            0 if self._trigger.action == ACTION_PRESS_KEY else 1
        )
        self._action.currentIndexChanged.connect(self._sync_visibility)
        self._action_key = QLineEdit(self._trigger.action_key)
        self._action_macro = QLineEdit(self._trigger.action_macro_path)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_macro)
        macro_row = QHBoxLayout()
        macro_row.addWidget(self._action_macro, 1)
        macro_row.addWidget(btn_browse)
        self._cooldown = _spin(0.0, 3600.0, self._trigger.cooldown_s, 0.1, 2)

        self._action_key_row = _labeled("Key:", self._action_key)
        self._action_macro_row = _labeled("Macro:", _wrap(macro_row))

        # Assemble.
        form = QFormLayout()
        form.addRow("Name:", self._name)
        form.addRow("Region:", _wrap(region_row))
        form.addRow("Detection:", self._detection)
        form.addRow(self._template_group)
        form.addRow(self._color_group)
        form.addRow("Condition:", self._condition)
        form.addRow("Action:", self._action)
        form.addRow(self._action_key_row)
        form.addRow(self._action_macro_row)
        form.addRow("Cooldown (s):", self._cooldown)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

        self._sync_visibility()

    # -- helpers ------------------------------------------------------------
    def _region_text(self) -> str:
        x, y, w, h = self._region
        return f"x={x}, y={y}, w={w}, h={h}"

    def _template_text(self) -> str:
        return "Snapshot: set ✓" if self._template_png else "Snapshot: (none)"

    def _select_region(self) -> None:
        sel = RegionSelector(self)
        if sel.exec() and sel.region:
            self._region = sel.region
            self._region_label.setText(self._region_text())

    def _capture_template(self) -> None:
        try:
            image = capture.grab_region(self._region)
            self._template_png = detector.encode_png(image)
            self._template_status.setText(self._template_text())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Capture failed", str(exc))

    def _browse_macro(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select macro", "", "Macro files (*.json);;All files (*)"
        )
        if path:
            self._action_macro.setText(path)

    def _rebuild_conditions(self) -> None:
        detection = self._detection.currentData()
        current = self._condition.currentData()
        self._condition.blockSignals(True)
        self._condition.clear()
        if detection == DETECT_TEMPLATE:
            self._condition.addItem("Reference absent (e.g. buff gone)", COND_ABSENT)
            self._condition.addItem("Reference present", COND_PRESENT)
        else:
            self._condition.addItem("Ratio above threshold (e.g. HP red)", COND_RATIO_ABOVE)
            self._condition.addItem("Ratio below threshold", COND_RATIO_BELOW)
        # Restore prior selection if still valid.
        idx = self._condition.findData(current)
        if idx < 0:
            idx = self._condition.findData(self._trigger.condition)
        self._condition.setCurrentIndex(max(0, idx))
        self._condition.blockSignals(False)

    def _sync_visibility(self) -> None:
        detection = self._detection.currentData()
        self._template_group.setVisible(detection == DETECT_TEMPLATE)
        self._color_group.setVisible(detection == DETECT_COLOR)
        self._rebuild_conditions()
        action = self._action.currentData()
        self._action_key_row.setVisible(action == ACTION_PRESS_KEY)
        self._action_macro_row.setVisible(action == ACTION_RUN_MACRO)

    def _accept(self) -> None:
        if self._detection.currentData() == DETECT_TEMPLATE and not self._template_png:
            QMessageBox.warning(
                self, "Missing snapshot",
                "Capture a reference snapshot from the region first.",
            )
            return
        self.accept()

    # -- result -------------------------------------------------------------
    def get_trigger(self) -> Trigger:
        t = self._trigger
        t.name = self._name.text() or "Trigger"
        t.region = self._region
        t.detection = self._detection.currentData()
        t.template_png = self._template_png
        t.match_threshold = float(self._match_threshold.value())
        t.hsv_lower = (self._h_lo.value(), self._s_lo.value(), self._v_lo.value())
        t.hsv_upper = (self._h_hi.value(), self._s_hi.value(), self._v_hi.value())
        t.condition = self._condition.currentData()
        t.ratio_threshold = float(self._ratio_threshold.value())
        t.action = self._action.currentData()
        t.action_key = self._action_key.text() or "1"
        t.action_macro_path = self._action_macro.text()
        t.cooldown_s = float(self._cooldown.value())
        return t


# -- small layout helpers ---------------------------------------------------
# TODO(audit): _wrap/_labeled are duplicated across trigger_dialog.py,
# buff_group_dialog.py and auto_input_dialog.py — move to a shared gui/util.py.
def _wrap(layout) -> QWidget:
    w = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    w.setLayout(layout)
    return w


def _labeled(text: str, widget: QWidget) -> QWidget:
    row = QHBoxLayout()
    row.addWidget(QLabel(text))
    row.addWidget(widget, 1)
    return _wrap(row)
