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
    QFileDialog,
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

from change_order import ChangeOrder, JointType, Op, Role, Scenario, Spec, Status
from change_order_builder import ChangeOrderBuilder
from change_order_store import export_change_order


@dataclass
class WeldRequest:
    kind: str
    op: str
    base: str | None = None
    spec: Spec = field(default_factory=Spec)


class ChangeOrderWizard(QDialog):
    """Thin Qt shell over ChangeOrderBuilder for the first new-wizard slice."""

    def __init__(self, builder=None, *, records_root=None, attachments_root=None):
        super().__init__()
        self.builder_template = builder if builder is not None else ChangeOrderBuilder()
        root = attachments_root if attachments_root is not None else records_root
        self.attachments_root = Path(root) if root is not None else Path.cwd() / "change_order_records"
        self.requests: list[WeldRequest] = []
        self.before_files: list[str] = []
        self.after_files: list[str] = []
        self.drawing_pdf_file: str | None = None
        self.material_requests: list[dict[str, Any]] = []
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
        for file in self.before_files:
            builder.add_photo(co, Role.BEFORE, file)
        for file in self.after_files:
            builder.add_photo(co, Role.AFTER, file)
        if self.drawing_pdf_file:
            builder.set_drawing_pdf(co, self.drawing_pdf_file)
        for material in self.material_requests:
            builder.add_material(co, **material)
        self.co = co
        self._current_builder = builder
        self._current_builder.compute_status(co)
        self._refresh_preview()
        self._refresh_attachments_preview()
        self._refresh_material_preview()
        self._refresh_status()
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

    def add_photo_file(self, role, file):
        text = "" if file is None else str(file).strip()
        if not text:
            return None
        if _enum_value(role) == Role.AFTER.value:
            self.after_files.append(text)
        else:
            self.before_files.append(text)
        self.rebuild_change_order()
        return text

    def remove_selected_photo(self):
        rows = sorted({index.row() for index in self.photo_table.selectedIndexes()}, reverse=True)
        if not rows and self.photo_table.currentRow() >= 0:
            rows = [self.photo_table.currentRow()]
        entries = self._photo_entries()
        for row in rows:
            if 0 <= row < len(entries):
                role, index = entries[row]
                if role == Role.AFTER.value:
                    del self.after_files[index]
                else:
                    del self.before_files[index]
        self.rebuild_change_order()

    def set_drawing_pdf_file(self, file):
        self.drawing_pdf_file = ("" if file is None else str(file).strip()) or None
        self.rebuild_change_order()

    def add_material_request(self):
        material = {
            "component": self.material_component_edit.text().strip() or None,
            "size": self.material_size_edit.text().strip() or None,
            "schedule": self.material_sch_edit.text().strip() or None,
            "material": self.material_material_edit.text().strip() or None,
            "qty": self.material_qty_edit.text().strip() or None,
            "unit": self.material_unit_edit.text().strip() or None,
            "remark": self.material_remark_edit.text().strip() or None,
        }
        if not any(value for value in material.values()):
            return None
        self.material_requests.append(material)
        for edit in (
            self.material_component_edit,
            self.material_size_edit,
            self.material_sch_edit,
            self.material_material_edit,
            self.material_qty_edit,
            self.material_unit_edit,
            self.material_remark_edit,
        ):
            edit.clear()
        self.rebuild_change_order()
        return material

    def remove_selected_material(self):
        rows = sorted({index.row() for index in self.material_table.selectedIndexes()}, reverse=True)
        if not rows and self.material_table.currentRow() >= 0:
            rows = [self.material_table.currentRow()]
        for row in rows:
            if 0 <= row < len(self.material_requests):
                del self.material_requests[row]
        self.rebuild_change_order()

    def save_draft(self) -> Path:
        co = self.rebuild_change_order()
        self._current_builder.finalize_id(co, self._existing_record_ids())
        result = export_change_order(co, self.attachments_root, overwrite=False)
        self.last_saved_path = result.record_path
        self.status_label.setText(f"已存草稿：{result.record_path}")
        return result.record_path

    def create_final(self) -> Path | None:
        co = self.rebuild_change_order()
        issues = self._current_builder.validate(co)
        if issues:
            self.status_label.setText("正式建立被擋：" + "；".join(issue["message"] for issue in issues))
            return None
        self._current_builder.compute_status(co)
        self._current_builder.finalize_id(co, self._existing_record_ids())
        result = export_change_order(co, self.attachments_root, overwrite=False)
        self.last_saved_path = result.record_path
        self.status_label.setText(f"正式建立完成：{result.record_path}")
        return result.record_path

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.addWidget(self._build_basic_group())
        root.addWidget(self._build_weld_input_group())
        root.addWidget(self._build_attachment_group())
        root.addWidget(self._build_material_group())

        self.weld_table = QTableWidget(0, 6)
        self.weld_table.setHorizontalHeaderLabels(["code", "base", "op", "spec", "source", "kind"])
        self.weld_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.weld_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.weld_table)

        button_row = QHBoxLayout()
        remove_button = QPushButton("移除選取焊口")
        remove_button.clicked.connect(self.remove_selected_request)
        self.save_button = QPushButton("存草稿")
        self.save_button.clicked.connect(self._save_clicked)
        self.final_button = QPushButton("正式建立")
        self.final_button.clicked.connect(self._final_clicked)
        self.status_label = QLabel("")
        button_row.addWidget(remove_button)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.final_button)
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

    def _build_attachment_group(self) -> QGroupBox:
        group = QGroupBox("照片 / 圖面")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        before_button = QPushButton("加入 before")
        before_button.clicked.connect(lambda: self._choose_photo(Role.BEFORE))
        after_button = QPushButton("加入 after")
        after_button.clicked.connect(lambda: self._choose_photo(Role.AFTER))
        remove_button = QPushButton("移除選取照片")
        remove_button.clicked.connect(self.remove_selected_photo)
        pdf_button = QPushButton("選擇圖面 PDF")
        pdf_button.clicked.connect(self._choose_pdf)
        row.addWidget(before_button)
        row.addWidget(after_button)
        row.addWidget(remove_button)
        row.addWidget(pdf_button)
        layout.addLayout(row)

        self.photo_table = QTableWidget(0, 2)
        self.photo_table.setHorizontalHeaderLabels(["role", "file"])
        self.photo_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.photo_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.photo_table)

        self.drawing_pdf_label = QLabel("圖面 PDF：未選")
        layout.addWidget(self.drawing_pdf_label)
        return group

    def _build_material_group(self) -> QGroupBox:
        group = QGroupBox("材料")
        layout = QVBoxLayout(group)
        form = QFormLayout()
        self.material_component_edit = QLineEdit()
        self.material_size_edit = QLineEdit()
        self.material_sch_edit = QLineEdit()
        self.material_material_edit = QLineEdit()
        self.material_qty_edit = QLineEdit()
        self.material_unit_edit = QLineEdit()
        self.material_remark_edit = QLineEdit()
        form.addRow("component", self.material_component_edit)
        form.addRow("size", self.material_size_edit)
        form.addRow("sch", self.material_sch_edit)
        form.addRow("material", self.material_material_edit)
        form.addRow("qty", self.material_qty_edit)
        form.addRow("unit", self.material_unit_edit)
        form.addRow("remark", self.material_remark_edit)
        layout.addLayout(form)

        row = QHBoxLayout()
        add_button = QPushButton("新增材料")
        add_button.clicked.connect(self.add_material_request)
        remove_button = QPushButton("移除選取材料")
        remove_button.clicked.connect(self.remove_selected_material)
        row.addWidget(add_button)
        row.addWidget(remove_button)
        row.addStretch(1)
        layout.addLayout(row)

        self.material_table = QTableWidget(0, 7)
        self.material_table.setHorizontalHeaderLabels(["component", "size", "sch", "material", "qty", "unit", "remark"])
        self.material_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.material_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.material_table)
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

    def _refresh_attachments_preview(self):
        entries = self._photo_entries()
        self.photo_table.setRowCount(len(entries))
        for row, (role, index) in enumerate(entries):
            file = self.after_files[index] if role == Role.AFTER.value else self.before_files[index]
            for col, value in enumerate([role, file]):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.photo_table.setItem(row, col, item)
        self.photo_table.resizeColumnsToContents()
        self.drawing_pdf_label.setText(f"圖面 PDF：{self.drawing_pdf_file or '未選'}")

    def _refresh_material_preview(self):
        self.material_table.setRowCount(len(self.material_requests))
        keys = ["component", "size", "schedule", "material", "qty", "unit", "remark"]
        for row, material in enumerate(self.material_requests):
            for col, key in enumerate(keys):
                item = QTableWidgetItem(str(material.get(key) or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.material_table.setItem(row, col, item)
        self.material_table.resizeColumnsToContents()

    def _refresh_status(self):
        if self.co is None or self._current_builder is None:
            self.status_label.setText("")
            return
        issues = self._current_builder.validate(self.co)
        status_text = _enum_value(self.co.status)
        if issues:
            self.status_label.setText(f"狀態：{status_text}｜缺漏：" + "；".join(issue["message"] for issue in issues))
        else:
            self.status_label.setText(f"狀態：{status_text}")

    def _existing_record_ids(self) -> list[str]:
        if not self.attachments_root.exists():
            return []
        return [path.name for path in self.attachments_root.iterdir() if path.is_dir()]

    def _photo_entries(self) -> list[tuple[str, int]]:
        return (
            [(Role.BEFORE.value, index) for index in range(len(self.before_files))]
            + [(Role.AFTER.value, index) for index in range(len(self.after_files))]
        )

    def _combo_op(self, combo: QComboBox) -> str:
        data = combo.currentData()
        return str(data if data is not None else combo.currentText())

    def _choose_photo(self, role):
        path, _filter = QFileDialog.getOpenFileName(self, "選擇照片")
        if path:
            self.add_photo_file(role, path)

    def _choose_pdf(self):
        path, _filter = QFileDialog.getOpenFileName(self, "選擇圖面 PDF", filter="PDF (*.pdf)")
        if path:
            self.set_drawing_pdf_file(path)

    def _save_clicked(self):
        try:
            self.save_draft()
        except Exception as exc:
            QMessageBox.critical(self, "存草稿失敗", str(exc))

    def _final_clicked(self):
        try:
            result = self.create_final()
            if result is None:
                QMessageBox.warning(self, "正式建立被擋", self.status_label.text())
        except Exception as exc:
            QMessageBox.critical(self, "正式建立失敗", str(exc))


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


def launch(builder=None, *, records_root=None, attachments_root=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = ChangeOrderWizard(builder=builder, records_root=records_root, attachments_root=attachments_root)
    return dialog.exec()


if __name__ == "__main__":
    raise SystemExit(launch())
