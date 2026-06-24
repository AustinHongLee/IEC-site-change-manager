# -*- coding: utf-8 -*-
"""Standalone source-driven ChangeOrder wizard slice."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from change_order import ChangeOrder, JointType, Op, Scenario, Spec, Status
from change_order_builder import ChangeOrderBuilder


@dataclass
class WeldRequest:
    kind: str
    op: str
    base: str | None = None
    spec: Spec = field(default_factory=Spec)


class ChangeOrderWizard(QDialog):
    """Thin Qt shell over ChangeOrderBuilder for the first new-wizard slice."""

    def __init__(self, builder=None, *, records_root=None):
        super().__init__()
        self.builder_template = builder if builder is not None else ChangeOrderBuilder()
        self.records_root = Path(records_root) if records_root is not None else Path.cwd() / "change_order_records"
        self.requests: list[WeldRequest] = []
        self.co: ChangeOrder | None = None
        self.last_saved_path: Path | None = None
        self._current_builder = None

        self.setWindowTitle("新修改單精靈")
        self.resize(900, 620)
        self._build_ui()
        self.rebuild_change_order()

    def rebuild_change_order(self) -> ChangeOrder:
        builder = self._fresh_builder()
        co = builder.start(
            normalize_series_raw(self.series_edit.text()),
            self.date_edit.text().strip(),
            scenario=Scenario.NORMAL,
        )
        builder.set_reason(co, self.reason_edit.toPlainText())
        for request in self.requests:
            if request.kind == "existing":
                builder.add_existing_weld(co, request.base, request.op, joint_type=JointType.WELD)
            elif request.kind == "new":
                builder.add_new_weld(co, request.op, request.spec, joint_type=JointType.WELD)
        self.co = co
        self._current_builder = builder
        self._refresh_preview()
        return co

    def add_existing_request(self):
        base = self.existing_base_edit.text().strip()
        if not base:
            return None
        self.requests.append(WeldRequest(kind="existing", base=base, op=self._combo_op(self.existing_op_combo)))
        self.existing_base_edit.clear()
        return self.rebuild_change_order().welds[-1]

    def add_new_request(self):
        spec = Spec(
            size=self.new_size_edit.text().strip() or None,
            sch=self.new_sch_edit.text().strip() or None,
            material=self.new_material_edit.text().strip() or None,
            weld_type=self.new_weld_type_edit.text().strip() or None,
        )
        self.requests.append(WeldRequest(kind="new", op=self._combo_op(self.new_op_combo), spec=spec))
        for edit in (self.new_size_edit, self.new_sch_edit, self.new_material_edit, self.new_weld_type_edit):
            edit.clear()
        return self.rebuild_change_order().welds[-1]

    def remove_selected_request(self):
        rows = sorted({index.row() for index in self.weld_table.selectedIndexes()}, reverse=True)
        if not rows and self.weld_table.currentRow() >= 0:
            rows = [self.weld_table.currentRow()]
        for row in rows:
            if 0 <= row < len(self.requests):
                del self.requests[row]
        self.rebuild_change_order()

    def save_draft(self) -> Path:
        co = self.rebuild_change_order()
        self._current_builder.compute_status(co)
        self._current_builder.finalize_id(co, self._existing_record_ids())
        output = self.records_root / (co.id or "") / "change_order.json"
        co.save_json(output)
        self.last_saved_path = output
        self.status_label.setText(f"已存草稿：{output}")
        return output

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.addWidget(self._build_basic_group())
        root.addWidget(self._build_weld_input_group())

        self.weld_table = QTableWidget(0, 6)
        self.weld_table.setHorizontalHeaderLabels(["code", "base", "op", "spec", "source", "kind"])
        self.weld_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.weld_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.weld_table)

        button_row = QHBoxLayout()
        remove_button = QPushButton("移除選取焊口")
        remove_button.clicked.connect(self.remove_selected_request)
        self.save_button = QPushButton("存草稿 JSON")
        self.save_button.clicked.connect(self._save_clicked)
        self.status_label = QLabel("")
        button_row.addWidget(remove_button)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)
        root.addLayout(button_row)
        root.addWidget(self.status_label)

    def _build_basic_group(self) -> QGroupBox:
        group = QGroupBox("基本資料")
        form = QFormLayout(group)
        self.series_edit = QLineEdit()
        self.series_edit.setObjectName("series_edit")
        self.series_edit.textChanged.connect(lambda _text: self.rebuild_change_order())
        self.date_edit = QLineEdit(datetime.now().strftime("%Y%m%d"))
        self.date_edit.setObjectName("date_edit")
        self.date_edit.textChanged.connect(lambda _text: self.rebuild_change_order())
        self.reason_edit = QTextEdit()
        self.reason_edit.setObjectName("reason_edit")
        self.reason_edit.setFixedHeight(70)
        self.reason_edit.textChanged.connect(self.rebuild_change_order)
        form.addRow("流水號", self.series_edit)
        form.addRow("日期", self.date_edit)
        form.addRow("原因", self.reason_edit)
        return group

    def _build_weld_input_group(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.addWidget(self._build_existing_group())
        layout.addWidget(self._build_new_group())
        return panel

    def _build_existing_group(self) -> QGroupBox:
        group = QGroupBox("既有焊口")
        form = QFormLayout(group)
        self.existing_base_edit = QLineEdit()
        self.existing_base_edit.setObjectName("existing_base_edit")
        self.existing_op_combo = _op_combo("existing_op_combo")
        add_button = QPushButton("新增既有焊口")
        add_button.clicked.connect(self.add_existing_request)
        form.addRow("base", self.existing_base_edit)
        form.addRow("操作", self.existing_op_combo)
        form.addRow(add_button)
        return group

    def _build_new_group(self) -> QGroupBox:
        group = QGroupBox("新焊口")
        form = QFormLayout(group)
        self.new_op_combo = _op_combo("new_op_combo")
        self.new_size_edit = QLineEdit()
        self.new_sch_edit = QLineEdit()
        self.new_material_edit = QLineEdit()
        self.new_weld_type_edit = QLineEdit()
        self.new_size_edit.setObjectName("new_size_edit")
        self.new_sch_edit.setObjectName("new_sch_edit")
        self.new_material_edit.setObjectName("new_material_edit")
        self.new_weld_type_edit.setObjectName("new_weld_type_edit")
        add_button = QPushButton("新增新焊口")
        add_button.clicked.connect(self.add_new_request)
        form.addRow("操作", self.new_op_combo)
        form.addRow("尺寸", self.new_size_edit)
        form.addRow("厚度", self.new_sch_edit)
        form.addRow("材質", self.new_material_edit)
        form.addRow("銲接型式", self.new_weld_type_edit)
        form.addRow(add_button)
        return group

    def _fresh_builder(self) -> ChangeOrderBuilder:
        template = self.builder_template
        lookup = getattr(template, "lookup", None)
        scheme = getattr(template, "scheme", None)
        clock = getattr(template, "clock", None)
        return ChangeOrderBuilder(lookup=lookup, scheme=scheme, clock=clock)

    def _refresh_preview(self):
        welds = self.co.welds if self.co is not None else []
        self.weld_table.setRowCount(len(welds))
        for row, weld in enumerate(welds):
            request = self.requests[row] if row < len(self.requests) else None
            spec_text = "/".join(filter(None, [
                weld.spec.size,
                weld.spec.sch,
                weld.spec.material,
                weld.spec.weld_type,
            ]))
            values = [
                weld.code or "",
                weld.base or "",
                _enum_value(weld.op) or "",
                spec_text,
                _enum_value(weld.spec_source) or "",
                request.kind if request is not None else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.weld_table.setItem(row, col, item)
        self.weld_table.resizeColumnsToContents()

    def _existing_record_ids(self) -> list[str]:
        if not self.records_root.exists():
            return []
        return [path.name for path in self.records_root.iterdir() if path.is_dir()]

    def _combo_op(self, combo: QComboBox) -> str:
        data = combo.currentData()
        return str(data if data is not None else combo.currentText())

    def _save_clicked(self):
        try:
            self.save_draft()
        except Exception as exc:
            QMessageBox.critical(self, "存草稿失敗", str(exc))


def normalize_series_raw(series: Any) -> str:
    text = "" if series is None else str(series).strip()
    return text.lstrip("0") or "0"


def _op_combo(object_name: str) -> QComboBox:
    combo = QComboBox()
    combo.setObjectName(object_name)
    for op in (Op.CUT, Op.EXTEND, Op.SHORTEN):
        combo.addItem(op.value, op.value)
    return combo


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def launch(builder=None, *, records_root=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = ChangeOrderWizard(builder=builder, records_root=records_root)
    return dialog.exec()


if __name__ == "__main__":
    raise SystemExit(launch())
