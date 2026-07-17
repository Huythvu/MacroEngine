"""Reusable vision-condition editor.

The block shared by the Vision Trigger dialog and the routine vision-step dialog:
region selection, detection kind (template/color), reference capture with
thumbnail, HSV band, condition combo, and a live preview + "Test now" readout.

Works against any object with Trigger-style vision fields (``region``,
``detection``, ``template_png``, ``match_threshold``, ``hsv_lower``,
``hsv_upper``, ``condition``, ``ratio_threshold``) — both :class:`Trigger` and
:class:`RoutineStep` qualify. Uses the same detector functions as the live
monitor/runner, so Test shows exactly what runtime will do.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..models.trigger import (
    COND_ABSENT,
    COND_PRESENT,
    COND_RATIO_ABOVE,
    COND_RATIO_BELOW,
    DETECT_COLOR,
    DETECT_TEMPLATE,
)
from ..vision import capture, detector
from .imaging import pixmap_from_png
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


def _wrap(layout) -> QWidget:
    w = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    w.setLayout(layout)
    return w


class ConditionWidget(QWidget):
    """Edits the vision fields of a Trigger-like object in place via
    :meth:`apply_to`; initial values are read from the object passed in."""

    def __init__(self, source, parent=None) -> None:
        super().__init__(parent)
        self._region = tuple(source.region)
        self._template_png = source.template_png

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Region.
        self._region_label = QLabel(self._region_text())
        btn_region = QPushButton("Select Region…")
        btn_region.clicked.connect(self._select_region)
        region_row = QHBoxLayout()
        region_row.addWidget(QLabel("Region:"))
        region_row.addWidget(self._region_label, 1)
        region_row.addWidget(btn_region)
        root.addLayout(region_row)

        # Detection kind.
        self._detection = QComboBox()
        self._detection.addItem("Template (image match)", DETECT_TEMPLATE)
        self._detection.addItem("Color (HSV ratio)", DETECT_COLOR)
        self._detection.setCurrentIndex(0 if source.detection == DETECT_TEMPLATE else 1)
        self._detection.currentIndexChanged.connect(self._sync_visibility)
        det_row = QHBoxLayout()
        det_row.addWidget(QLabel("Detection:"))
        det_row.addWidget(self._detection, 1)
        root.addLayout(det_row)

        # Template group.
        self._tpl_thumb = QLabel()
        self._tpl_thumb.setFixedSize(56, 56)
        self._tpl_thumb.setAlignment(Qt.AlignCenter)
        self._refresh_tpl_thumb()
        btn_capture = QPushButton("Capture Snapshot from Region")
        btn_capture.clicked.connect(self._capture_template)
        self._match_threshold = _spin(0.0, 1.0, source.match_threshold, 0.05, 2)
        cap_row = QHBoxLayout()
        cap_row.addWidget(self._tpl_thumb)
        cap_row.addWidget(btn_capture, 1)
        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel("Match threshold:"))
        thr_row.addWidget(self._match_threshold, 1)
        tpl_col = QVBoxLayout()
        tpl_col.addLayout(cap_row)
        tpl_col.addLayout(thr_row)
        self._template_group = QGroupBox("Template settings — the reference image")
        self._template_group.setLayout(tpl_col)
        root.addWidget(self._template_group)

        # Color group.
        self._h_lo = _spin(0, 179, source.hsv_lower[0])
        self._s_lo = _spin(0, 255, source.hsv_lower[1])
        self._v_lo = _spin(0, 255, source.hsv_lower[2])
        self._h_hi = _spin(0, 179, source.hsv_upper[0])
        self._s_hi = _spin(0, 255, source.hsv_upper[1])
        self._v_hi = _spin(0, 255, source.hsv_upper[2])
        self._ratio_threshold = _spin(0.0, 1.0, source.ratio_threshold, 0.05, 2)
        lo_row = QHBoxLayout()
        lo_row.addWidget(QLabel("HSV lower:"))
        for w in (self._h_lo, self._s_lo, self._v_lo):
            lo_row.addWidget(w)
        hi_row = QHBoxLayout()
        hi_row.addWidget(QLabel("HSV upper:"))
        for w in (self._h_hi, self._s_hi, self._v_hi):
            hi_row.addWidget(w)
        rt_row = QHBoxLayout()
        rt_row.addWidget(QLabel("Ratio threshold:"))
        rt_row.addWidget(self._ratio_threshold, 1)
        color_col = QVBoxLayout()
        color_col.addLayout(lo_row)
        color_col.addLayout(hi_row)
        color_col.addLayout(rt_row)
        self._color_group = QGroupBox("Color settings")
        self._color_group.setLayout(color_col)
        root.addWidget(self._color_group)

        # Condition.
        self._condition = QComboBox()
        self._initial_condition = source.condition
        cond_row = QHBoxLayout()
        cond_row.addWidget(QLabel("Condition:"))
        cond_row.addWidget(self._condition, 1)
        root.addLayout(cond_row)

        # Live preview & test.
        self._preview = QLabel("(no preview)")
        self._preview.setMinimumSize(180, 90)
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setStyleSheet("border: 1px solid palette(mid);")
        self._test_label = QLabel("—")
        self._test_label.setWordWrap(True)
        btn_test = QPushButton("Test now")
        btn_test.clicked.connect(self.test)
        pv_side = QVBoxLayout()
        pv_side.addWidget(btn_test)
        pv_side.addWidget(self._test_label, 1)
        pv_side.addStretch(1)
        pv_row = QHBoxLayout()
        pv_row.addWidget(self._preview)
        pv_row.addLayout(pv_side, 1)
        preview_group = QGroupBox("Live preview & test")
        preview_group.setLayout(pv_row)
        root.addWidget(preview_group)

        self._sync_visibility()

    # -- accessors -----------------------------------------------------------
    @property
    def has_template(self) -> bool:
        return self._template_png is not None

    @property
    def detection_kind(self) -> str:
        return self._detection.currentData()

    def apply_to(self, target) -> None:
        """Write the edited vision fields onto ``target`` (Trigger or step)."""
        target.region = self._region
        target.detection = self._detection.currentData()
        target.template_png = self._template_png
        target.match_threshold = float(self._match_threshold.value())
        target.hsv_lower = (self._h_lo.value(), self._s_lo.value(), self._v_lo.value())
        target.hsv_upper = (self._h_hi.value(), self._s_hi.value(), self._v_hi.value())
        target.condition = self._condition.currentData()
        target.ratio_threshold = float(self._ratio_threshold.value())

    # -- internals -----------------------------------------------------------
    def _region_text(self) -> str:
        x, y, w, h = self._region
        return f"x={x}, y={y}, w={w}, h={h}"

    def _refresh_tpl_thumb(self) -> None:
        pm = pixmap_from_png(self._template_png, 54)
        if pm.isNull():
            self._tpl_thumb.setText("(none)")
        else:
            self._tpl_thumb.setPixmap(pm)

    def _select_region(self) -> None:
        sel = RegionSelector(self)
        if sel.exec() and sel.region:
            self._region = sel.region
            self._region_label.setText(self._region_text())

    def _capture_template(self) -> None:
        try:
            image = capture.grab_region(self._region)
            self._template_png = detector.encode_png(image)
            self._refresh_tpl_thumb()
            self.test()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Capture failed", str(exc))

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
        idx = self._condition.findData(current)
        if idx < 0:
            idx = self._condition.findData(self._initial_condition)
        self._condition.setCurrentIndex(max(0, idx))
        self._condition.blockSignals(False)

    def _sync_visibility(self) -> None:
        detection = self._detection.currentData()
        self._template_group.setVisible(detection == DETECT_TEMPLATE)
        self._color_group.setVisible(detection == DETECT_COLOR)
        self._rebuild_conditions()

    def test(self) -> None:
        """Grab the region now, show it, and report whether the condition fires."""
        try:
            image = capture.grab_region(self._region)
        except Exception as exc:  # noqa: BLE001
            self._test_label.setText(f"error: {exc}")
            return
        try:
            self._preview.setPixmap(pixmap_from_png(detector.encode_png(image), 180))
        except Exception:  # noqa: BLE001
            pass
        if self._detection.currentData() == DETECT_TEMPLATE:
            if not self._template_png:
                self._test_label.setText("Capture a snapshot first")
                return
            present, score = detector.template_present(
                image, self._template_png, self._match_threshold.value()
            )
            cond = self._condition.currentData()
            met = present if cond == COND_PRESENT else (not present)
            state = "present" if present else "absent"
            self._test_label.setText(
                f"reference {state} (score {score:.2f}) → {'FIRE' if met else 'no'}"
            )
        else:
            ratio = detector.color_ratio(
                image,
                (self._h_lo.value(), self._s_lo.value(), self._v_lo.value()),
                (self._h_hi.value(), self._s_hi.value(), self._v_hi.value()),
            )
            cond = self._condition.currentData()
            met = ratio > self._ratio_threshold.value() if cond == COND_RATIO_ABOVE \
                else ratio < self._ratio_threshold.value()
            self._test_label.setText(f"match ratio {ratio:.2f} → {'FIRE' if met else 'no'}")
