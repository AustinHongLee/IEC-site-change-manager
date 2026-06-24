# -*- coding: utf-8 -*-
"""Standalone source-driven ChangeOrder wizard slice."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from change_order import ChangeOrder, JointType, Op, Role, Scenario, Spec, Status
from change_order_builder import ChangeOrderBuilder
from change_order_store import export_change_order
from staging_manager import scan_staging
from theme import Colors, Fonts, build_stylesheet, make_hint_label, make_separator, set_button_role


HISTORY_PREVIEW_ROLE = Qt.ItemDataRole.UserRole.value + 1
IMAGE_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


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
        self.staging_root = self.attachments_root.parent / "staging"
        self.requests: list[WeldRequest] = []
        self.before_files: list[str] = []
        self.after_files: list[str] = []
        self.drawing_pdf_file: str | None = None
        self.material_requests: list[dict[str, Any]] = []
        self.co: ChangeOrder | None = None
        self.last_saved_path: Path | None = None
        self._current_builder = None

        self.setWindowTitle("新修改單精靈")
        self.setStyleSheet(build_stylesheet())
        self.setFont(Fonts.body())
        self.resize(860, 600)
        self.setMinimumSize(700, 500)
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
        authorization = self._authorization_fields()
        if any(value for value in authorization.values()):
            builder.set_authorization(co, **authorization)
        self.co = co
        self._current_builder = builder
        self._current_builder.compute_status(co, required=self._required_keys())
        self._refresh_source_welds()
        self._refresh_preview()
        self._refresh_attachments_preview()
        self._refresh_material_preview()
        self._refresh_status()
        self._refresh_sidebar()
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
        self._refresh_history()
        return result.record_path

    def create_final(self) -> Path | None:
        co = self.rebuild_change_order()
        issues = self._current_builder.validate(co, required=self._required_keys())
        if issues:
            self.status_label.setText("正式建立被擋：還缺：" + "、".join(_issue_text(issue) for issue in issues))
            return None
        self._current_builder.compute_status(co, required=self._required_keys())
        self._current_builder.finalize_id(co, self._existing_record_ids())
        result = export_change_order(co, self.attachments_root, overwrite=False)
        self.last_saved_path = result.record_path
        self.status_label.setText(f"正式建立完成：{result.record_path}")
        self._refresh_history()
        return result.record_path

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._make_tab(self._build_basic_group()), "① 基本資料")
        self.tabs.addTab(self._make_tab(
            _hint("從管制表挑既有焊口改（填原始焊口＋操作），或加全新焊口；編號系統自動算"),
            self._build_weld_input_group(),
            self._build_weld_table_group(),
        ), "② 焊口")
        self.tabs.addTab(self._make_tab(
            _hint("修改前(問題)、修改後(完成)各至少 1 張，並附圖面 PDF"),
            self._build_attachment_group(),
        ), "③ 照片與圖面")
        self.tabs.addTab(self._make_tab(
            _hint("列出本次修改單要記錄的材料；沒有材料時可先留空存草稿"),
            self._build_material_group(),
        ), "④ 材料")

        main_pane = QWidget()
        main_layout = QVBoxLayout(main_pane)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.tabs)

        self.sidebar = self._build_sidebar()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(main_pane)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([620, 240])
        root.addWidget(self.splitter, 1)
        root.addWidget(make_separator())
        root.addWidget(self._build_action_bar())
        self._refresh_staging()

    def _build_weld_table_group(self) -> QGroupBox:
        group = QGroupBox("焊口清單")
        layout = QVBoxLayout(group)
        self.weld_table = QTableWidget(0, 6)
        self.weld_table.setHorizontalHeaderLabels(["焊口碼", "原始", "操作", "規格", "來源", "類型"])
        self.weld_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.weld_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.weld_table.verticalHeader().setVisible(False)
        self.weld_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.weld_table)
        self.weld_empty_label = make_hint_label("尚未加入焊口")
        layout.addWidget(self.weld_empty_label)

        row = QHBoxLayout()
        remove_button = QPushButton("移除選取焊口")
        remove_button.clicked.connect(self.remove_selected_request)
        row.addWidget(remove_button)
        row.addStretch(1)
        layout.addLayout(row)
        return group

    def _build_action_bar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame {{ background: {Colors.BG_WHITE}; border: 1px solid {Colors.BORDER_LIGHT};"
            " border-radius: 8px; padding: 6px; }}"
        )
        button_row = QHBoxLayout(bar)
        button_row.setContentsMargins(8, 6, 8, 6)
        button_row.setSpacing(8)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusBar")
        self.status_label.setWordWrap(True)
        self.status_label.setFont(Fonts.small())
        self.sidebar_toggle_button = QPushButton("收合側欄")
        self.sidebar_toggle_button.setObjectName("sidebar_toggle_button")
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)
        set_button_role(self.sidebar_toggle_button, "flat")
        self.save_button = QPushButton("存草稿")
        self.save_button.clicked.connect(self._save_clicked)
        self.final_button = QPushButton("正式建立")
        set_button_role(self.final_button, "primary")
        self.final_button.clicked.connect(self._final_clicked)
        button_row.addWidget(self.sidebar_toggle_button)
        button_row.addWidget(self.status_label, 1)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.final_button)
        return bar

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("change_order_sidebar")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(320)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("輔助側欄")
        title.setFont(Fonts.subheading())
        title.setStyleSheet(f"color: {Colors.PRIMARY};")
        layout.addWidget(title)
        layout.addWidget(self._build_history_group())
        layout.addWidget(self._build_selected_preview_group())
        layout.addWidget(self._build_staging_group())
        layout.addStretch(1)
        return sidebar

    def _build_history_group(self) -> QGroupBox:
        group = QGroupBox("歷史")
        layout = QVBoxLayout(group)
        self.history_table = QTableWidget(0, 4)
        self.history_table.setObjectName("history_table")
        self.history_table.setHorizontalHeaderLabels(["修改單", "日期", "焊口", "狀態"])
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setMaximumHeight(130)
        self.history_table.itemSelectionChanged.connect(self._refresh_history_preview)
        layout.addWidget(self.history_table)
        self.history_empty_label = make_hint_label("填流水號後顯示新系統歷史")
        layout.addWidget(self.history_empty_label)
        self.history_preview_label = QLabel("選擇一筆歷史")
        self.history_preview_label.setObjectName("history_preview_label")
        self.history_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_preview_label.setFixedHeight(86)
        self.history_preview_label.setFrameShape(QFrame.Shape.StyledPanel)
        layout.addWidget(self.history_preview_label)
        self.history_detail_label = make_hint_label("選取歷史後會顯示焊口、狀態與照片縮圖。")
        self.history_detail_label.setObjectName("history_detail_label")
        self.history_detail_label.setWordWrap(True)
        layout.addWidget(self.history_detail_label)
        row = QHBoxLayout()
        open_button = QPushButton("開資料夾")
        open_button.setObjectName("open_history_folder_button")
        open_button.clicked.connect(self.open_selected_history_folder)
        row.addWidget(open_button)
        row.addStretch(1)
        layout.addLayout(row)
        return group

    def _build_selected_preview_group(self) -> QGroupBox:
        group = QGroupBox("已選預覽")
        layout = QVBoxLayout(group)
        self.selected_preview_table = QTableWidget(0, 3)
        self.selected_preview_table.setObjectName("selected_preview_table")
        self.selected_preview_table.setHorizontalHeaderLabels(["類型", "內容", "狀態"])
        self.selected_preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.selected_preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.selected_preview_table.verticalHeader().setVisible(False)
        self.selected_preview_table.horizontalHeader().setStretchLastSection(True)
        self.selected_preview_table.setMaximumHeight(160)
        self.selected_preview_table.itemSelectionChanged.connect(self._refresh_selected_preview_detail)
        layout.addWidget(self.selected_preview_table)
        self.selected_preview_empty_label = make_hint_label("尚未選取焊口、照片、PDF 或材料")
        layout.addWidget(self.selected_preview_empty_label)

        self.selected_preview_image_label = QLabel("選擇一筆照片、PDF 或材料")
        self.selected_preview_image_label.setObjectName("selected_preview_image_label")
        self.selected_preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_preview_image_label.setFixedHeight(110)
        self.selected_preview_image_label.setFrameShape(QFrame.Shape.StyledPanel)
        layout.addWidget(self.selected_preview_image_label)
        self.selected_preview_detail_label = make_hint_label("選取側欄項目後會顯示檔名、狀態與縮圖。")
        self.selected_preview_detail_label.setObjectName("selected_preview_detail_label")
        self.selected_preview_detail_label.setWordWrap(True)
        layout.addWidget(self.selected_preview_detail_label)

        row = QHBoxLayout()
        annotate_button = QPushButton("標註選取")
        annotate_button.setObjectName("annotate_selected_button")
        annotate_button.clicked.connect(self.annotate_selected_preview)
        row.addWidget(annotate_button)
        row.addStretch(1)
        layout.addLayout(row)
        return group

    def _build_staging_group(self) -> QGroupBox:
        group = QGroupBox("staging")
        layout = QVBoxLayout(group)
        self.staging_hint_label = make_hint_label(f"來源：{self.staging_root}")
        self.staging_hint_label.setWordWrap(True)
        layout.addWidget(self.staging_hint_label)
        self.staging_table = QTableWidget(0, 3)
        self.staging_table.setObjectName("staging_table")
        self.staging_table.setHorizontalHeaderLabels(["檔案", "類型", "時間"])
        self.staging_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.staging_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.staging_table.verticalHeader().setVisible(False)
        self.staging_table.horizontalHeader().setStretchLastSection(True)
        self.staging_table.setMaximumHeight(130)
        layout.addWidget(self.staging_table)
        self.staging_empty_label = make_hint_label("staging/ 目前沒有照片或 PDF")
        layout.addWidget(self.staging_empty_label)

        refresh_row = QHBoxLayout()
        refresh_button = QPushButton("重新整理")
        refresh_button.clicked.connect(self._refresh_staging)
        open_staging_button = QPushButton("開 staging")
        open_staging_button.setObjectName("open_staging_folder_button")
        open_staging_button.clicked.connect(self.open_staging_folder)
        refresh_row.addWidget(refresh_button)
        refresh_row.addWidget(open_staging_button)
        refresh_row.addStretch(1)
        layout.addLayout(refresh_row)

        action_row = QHBoxLayout()
        before_button = QPushButton("加入前")
        before_button.clicked.connect(lambda: self._add_selected_staging_photo(Role.BEFORE))
        after_button = QPushButton("加入後")
        after_button.clicked.connect(lambda: self._add_selected_staging_photo(Role.AFTER))
        pdf_button = QPushButton("設 PDF")
        pdf_button.clicked.connect(self._set_selected_staging_pdf)
        action_row.addWidget(before_button)
        action_row.addWidget(after_button)
        action_row.addWidget(pdf_button)
        layout.addLayout(action_row)
        return group

    def _build_basic_group(self) -> QGroupBox:
        group = QGroupBox("基本資料")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.series_edit = QLineEdit()
        self.series_edit.setObjectName("series_edit")
        self.series_edit.setPlaceholderText("例如：88")
        self.series_edit.textChanged.connect(lambda _text: self.rebuild_change_order())
        self.date_edit = QLineEdit(datetime.now().strftime("%Y%m%d"))
        self.date_edit.setObjectName("date_edit")
        self.date_edit.setPlaceholderText("YYYYMMDD")
        self.date_edit.textChanged.connect(lambda _text: self.rebuild_change_order())
        self.reason_edit = QTextEdit()
        self.reason_edit.setObjectName("reason_edit")
        self.reason_edit.setPlaceholderText("簡述現場修改原因")
        self.reason_edit.setFixedHeight(96)
        self.reason_edit.textChanged.connect(self.rebuild_change_order)
        form.addRow("流水號", self.series_edit)
        form.addRow("日期", self.date_edit)
        form.addRow("修改原因", self.reason_edit)

        self.authorization_name_edit = QLineEdit()
        self.authorization_name_edit.setObjectName("authorization_name_edit")
        self.authorization_name_edit.setPlaceholderText("業主或代表姓名")
        self.authorization_name_edit.textChanged.connect(lambda _text: self.rebuild_change_order())
        self.authorization_at_edit = QLineEdit()
        self.authorization_at_edit.setObjectName("authorization_at_edit")
        self.authorization_at_edit.setPlaceholderText("簽認日期 / 時間")
        self.authorization_at_edit.textChanged.connect(lambda _text: self.rebuild_change_order())
        self.authorization_evidence_edit = QLineEdit()
        self.authorization_evidence_edit.setObjectName("authorization_evidence_edit")
        self.authorization_evidence_edit.setPlaceholderText("簽認表單、照片或備註")
        self.authorization_evidence_edit.textChanged.connect(lambda _text: self.rebuild_change_order())
        form.addRow("簽認人", self.authorization_name_edit)
        form.addRow("簽認時間", self.authorization_at_edit)
        form.addRow("簽認佐證", self.authorization_evidence_edit)

        required_row = QHBoxLayout()
        self.require_materials_checkbox = QCheckBox("材料必填")
        self.require_materials_checkbox.setObjectName("require_materials_checkbox")
        self.require_authorization_checkbox = QCheckBox("簽認必填")
        self.require_authorization_checkbox.setObjectName("require_authorization_checkbox")
        self.require_reason_checkbox = QCheckBox("原因必填")
        self.require_reason_checkbox.setObjectName("require_reason_checkbox")
        self.require_welds_checkbox = QCheckBox("焊口必填")
        self.require_welds_checkbox.setObjectName("require_welds_checkbox")
        for checkbox in (
            self.require_materials_checkbox,
            self.require_authorization_checkbox,
            self.require_reason_checkbox,
            self.require_welds_checkbox,
        ):
            checkbox.stateChanged.connect(lambda _state: self.rebuild_change_order())
            required_row.addWidget(checkbox)
        required_row.addStretch(1)
        form.addRow("正式條件", required_row)
        return group

    def _build_weld_input_group(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._build_existing_group())
        layout.addWidget(self._build_new_group())
        return panel

    def _build_existing_group(self) -> QGroupBox:
        group = QGroupBox("既有焊口")
        layout = QVBoxLayout(group)
        layout.addWidget(_hint("填流水號後，從這張圖號的管制表焊口清單挑一筆，再選操作加入修改"))

        self.source_filter_edit = QLineEdit()
        self.source_filter_edit.setObjectName("source_filter_edit")
        self.source_filter_edit.setPlaceholderText("搜尋焊口號 / 尺寸 / 材質")
        self.source_filter_edit.textChanged.connect(lambda _text: self._refresh_source_welds())
        layout.addWidget(self.source_filter_edit)

        self.source_weld_table = QTableWidget(0, 6)
        self.source_weld_table.setObjectName("source_weld_table")
        self.source_weld_table.setHorizontalHeaderLabels(["現有焊口", "原始", "尺寸", "SCH", "材質", "型式"])
        self.source_weld_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.source_weld_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.source_weld_table.verticalHeader().setVisible(False)
        self.source_weld_table.horizontalHeader().setStretchLastSection(True)
        self.source_weld_table.setMaximumHeight(180)
        self.source_weld_table.itemSelectionChanged.connect(self._source_weld_selection_changed)
        self.source_weld_table.cellDoubleClicked.connect(lambda _row, _col: self.add_existing_request())
        layout.addWidget(self.source_weld_table)

        self.source_weld_empty_label = make_hint_label("填流水號後載入這張圖的既有焊口")
        layout.addWidget(self.source_weld_empty_label)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.existing_base_edit = QLineEdit()
        self.existing_base_edit.setObjectName("existing_base_edit")
        self.existing_base_edit.setPlaceholderText("從上方清單帶入；也可手填")
        self.existing_op_combo = _op_combo("existing_op_combo")
        add_button = QPushButton("新增既有焊口")
        add_button.clicked.connect(self.add_existing_request)
        form.addRow("原始焊口", self.existing_base_edit)
        form.addRow("操作", self.existing_op_combo)
        form.addRow(add_button)
        layout.addLayout(form)
        return group

    def _build_attachment_group(self) -> QGroupBox:
        group = QGroupBox("照片 / 圖面")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        before_button = QPushButton("加入修改前")
        before_button.clicked.connect(lambda: self._choose_photo(Role.BEFORE))
        after_button = QPushButton("加入修改後")
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
        self.photo_table.setHorizontalHeaderLabels(["角色", "檔案"])
        self.photo_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.photo_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.photo_table.verticalHeader().setVisible(False)
        self.photo_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.photo_table)
        self.photo_empty_label = make_hint_label("尚未加入照片")
        layout.addWidget(self.photo_empty_label)

        self.drawing_pdf_label = QLabel("圖面 PDF：未選")
        self.drawing_pdf_label.setFont(Fonts.small())
        self.drawing_pdf_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(self.drawing_pdf_label)
        return group

    def _build_material_group(self) -> QGroupBox:
        group = QGroupBox("材料")
        layout = QVBoxLayout(group)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.material_component_edit = QLineEdit()
        self.material_size_edit = QLineEdit()
        self.material_sch_edit = QLineEdit()
        self.material_material_edit = QLineEdit()
        self.material_qty_edit = QLineEdit()
        self.material_unit_edit = QLineEdit()
        self.material_remark_edit = QLineEdit()
        self.material_component_edit.setPlaceholderText("例如：Pipe")
        self.material_size_edit.setPlaceholderText('例如：2"')
        self.material_sch_edit.setPlaceholderText("例如：SCH40")
        self.material_material_edit.setPlaceholderText("例如：SUS304")
        self.material_qty_edit.setPlaceholderText("例如：2")
        self.material_unit_edit.setPlaceholderText("例如：M")
        self.material_remark_edit.setPlaceholderText("補充說明")
        form.addRow("零件", self.material_component_edit)
        form.addRow("尺寸", self.material_size_edit)
        form.addRow("SCH", self.material_sch_edit)
        form.addRow("材質", self.material_material_edit)
        form.addRow("數量", self.material_qty_edit)
        form.addRow("單位", self.material_unit_edit)
        form.addRow("備註", self.material_remark_edit)
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
        self.material_table.setHorizontalHeaderLabels(["零件", "尺寸", "SCH", "材質", "數量", "單位", "備註"])
        self.material_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.material_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.material_table.verticalHeader().setVisible(False)
        self.material_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.material_table)
        self.material_empty_label = make_hint_label("尚未加入材料")
        layout.addWidget(self.material_empty_label)
        return group

    def _build_new_group(self) -> QGroupBox:
        group = QGroupBox("新焊口")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.new_op_combo = _op_combo("new_op_combo")
        self.new_size_edit = QLineEdit()
        self.new_sch_edit = QLineEdit()
        self.new_material_edit = QLineEdit()
        self.new_weld_type_edit = QLineEdit()
        self.new_size_edit.setObjectName("new_size_edit")
        self.new_sch_edit.setObjectName("new_sch_edit")
        self.new_material_edit.setObjectName("new_material_edit")
        self.new_weld_type_edit.setObjectName("new_weld_type_edit")
        self.new_size_edit.setPlaceholderText('例如：2"')
        self.new_sch_edit.setPlaceholderText("例如：SCH40")
        self.new_material_edit.setPlaceholderText("例如：SUS304")
        self.new_weld_type_edit.setPlaceholderText("例如：BW")
        add_button = QPushButton("新增新焊口")
        add_button.clicked.connect(self.add_new_request)
        form.addRow("操作", self.new_op_combo)
        form.addRow("尺寸", self.new_size_edit)
        form.addRow("SCH", self.new_sch_edit)
        form.addRow("材質", self.new_material_edit)
        form.addRow("銲接型式", self.new_weld_type_edit)
        form.addRow(add_button)
        return group

    def _make_tab(self, *widgets: QWidget) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def toggle_sidebar(self):
        visible = self.sidebar.isHidden()
        self.sidebar.setVisible(visible)
        self.sidebar_toggle_button.setText("收合側欄" if visible else "顯示側欄")
        if visible:
            self.splitter.setSizes([620, 240])

    def _refresh_sidebar(self):
        if not hasattr(self, "history_table"):
            return
        self._refresh_history()
        self._refresh_selected_preview()

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
                _spec_source_text(weld.spec_source),
                _request_kind_text(request.kind if request is not None else ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.weld_table.setItem(row, col, item)
        self.weld_table.resizeColumnsToContents()
        self.weld_empty_label.setVisible(len(welds) == 0)

    def _refresh_source_welds(self):
        if not hasattr(self, "source_weld_table"):
            return

        self.source_weld_table.setRowCount(0)
        series = normalize_series_raw(self.series_edit.text())
        if not self.series_edit.text().strip():
            self.source_weld_empty_label.setText("填流水號後載入這張圖的既有焊口")
            self.source_weld_empty_label.setVisible(True)
            return

        lookup = getattr(self.builder_template, "lookup", None)
        if lookup is None:
            self.source_weld_empty_label.setText("沒有可用的管制表查詢來源")
            self.source_weld_empty_label.setVisible(True)
            return

        try:
            rows = self._source_weld_rows(lookup, series)
        except Exception as exc:
            self.source_weld_empty_label.setText(f"焊口清單載入失敗：{exc}")
            self.source_weld_empty_label.setVisible(True)
            return

        query = self.source_filter_edit.text().strip().lower()
        if query:
            rows = [row for row in rows if query in " ".join(str(value).lower() for value in row).lower()]

        self.source_weld_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col, value in enumerate(row):
                item = QTableWidgetItem(str(value or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row[1])
                self.source_weld_table.setItem(row_index, col, item)
        self.source_weld_table.resizeColumnsToContents()
        self.source_weld_empty_label.setText("沒有符合的既有焊口" if query else "這張圖目前沒有可列出的既有焊口")
        self.source_weld_empty_label.setVisible(len(rows) == 0)

    def _source_weld_rows(self, lookup, series: str) -> list[list[str]]:
        rows = []
        for weld_id in lookup.existing_weld_ids(series):
            base = _source_base_for_weld_id(weld_id)
            spec = lookup.lookup_spec(series, weld_id) or lookup.lookup_spec(series, base) or Spec()
            rows.append([
                str(weld_id),
                base,
                spec.size or "",
                spec.sch or "",
                spec.material or "",
                spec.weld_type or "",
            ])
        return rows

    def _source_weld_selection_changed(self):
        row = self.source_weld_table.currentRow()
        if row < 0:
            return
        item = self.source_weld_table.item(row, 0)
        if item is None:
            return
        base = item.data(Qt.ItemDataRole.UserRole) or item.text()
        self.existing_base_edit.setText(str(base))

    def open_selected_history_folder(self):
        row = self.history_table.currentRow()
        if row < 0:
            self.status_label.setText("請先選擇一筆歷史")
            return None
        item = self.history_table.item(row, 0)
        if item is None:
            self.status_label.setText("請先選擇一筆歷史")
            return None
        folder = item.data(Qt.ItemDataRole.UserRole)
        if not folder:
            self.status_label.setText("這筆歷史沒有資料夾路徑")
            return None
        self._open_path(folder)
        self.status_label.setText(f"已開啟歷史資料夾：{Path(str(folder)).name}")
        return str(folder)

    def open_staging_folder(self):
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self._open_path(self.staging_root)
        self.status_label.setText(f"已開啟 staging：{self.staging_root}")
        self._refresh_staging()
        return str(self.staging_root)

    def _open_path(self, path):
        os.startfile(str(path))

    def _refresh_history(self):
        if not hasattr(self, "history_table"):
            return
        records = self._history_records()
        self.history_table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            values = [record["id"], record["date"], record["welds"], record["status"]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record["folder"])
                    item.setData(HISTORY_PREVIEW_ROLE, record.get("preview", ""))
                self.history_table.setItem(row_index, col, item)
        self.history_table.resizeColumnsToContents()
        self.history_empty_label.setText(
            "填流水號後顯示新系統歷史" if not self.series_edit.text().strip() else "這張圖目前沒有新系統歷史"
        )
        self.history_empty_label.setVisible(len(records) == 0)
        if records and self.history_table.currentRow() < 0:
            self.history_table.selectRow(0)
        self._refresh_history_preview()

    def _history_records(self) -> list[dict[str, str]]:
        series = normalize_series_raw(self.series_edit.text())
        if not self.series_edit.text().strip() or not self.attachments_root.exists():
            return []
        records: list[dict[str, str]] = []
        records.extend(self._new_history_records(series))
        records.extend(self._legacy_history_records(series))
        return sorted(records, key=lambda row: (row["date"], row["id"]), reverse=True)

    def _new_history_records(self, series: str) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for record_path in self.attachments_root.glob("*/change_order.json"):
            try:
                co = ChangeOrder.load_json(record_path)
            except Exception:
                continue
            if str(co.series or "") != series:
                continue
            welds = "、".join(weld.code or "" for weld in co.welds if weld.code)
            records.append({
                "id": co.id or record_path.parent.name,
                "date": co.date or "",
                "welds": welds or "-",
                "status": _status_text(co.status),
                "folder": str(record_path.parent),
                "preview": _first_change_order_photo(record_path.parent, co),
            })
        return records

    def _legacy_history_records(self, series: str) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for date_dir in self.attachments_root.iterdir():
            if not date_dir.is_dir() or not _looks_like_date_folder(date_dir.name):
                continue
            for folder in date_dir.iterdir():
                if not folder.is_dir():
                    continue
                prefix, suffix = _split_legacy_folder_name(folder.name)
                if not _same_series(prefix, series):
                    continue
                records.append({
                    "id": folder.name,
                    "date": date_dir.name,
                    "welds": suffix or "-",
                    "status": "舊資料",
                    "folder": str(folder),
                    "preview": _first_image_in_folder(folder),
                })
        return records

    def _refresh_history_preview(self):
        if not hasattr(self, "history_preview_label"):
            return
        row = self.history_table.currentRow()
        if row < 0:
            self._set_history_preview_text("選擇一筆歷史", "選取歷史後會顯示焊口、狀態與照片縮圖。")
            return

        id_item = self.history_table.item(row, 0)
        date_item = self.history_table.item(row, 1)
        weld_item = self.history_table.item(row, 2)
        status_item = self.history_table.item(row, 3)
        if id_item is None:
            self._set_history_preview_text("選擇一筆歷史", "選取歷史後會顯示焊口、狀態與照片縮圖。")
            return

        preview = id_item.data(HISTORY_PREVIEW_ROLE)
        detail = (
            f"{id_item.text()}｜{date_item.text() if date_item else '-'}｜"
            f"焊口：{weld_item.text() if weld_item else '-'}｜{status_item.text() if status_item else '-'}"
        )
        if not preview:
            self._set_history_preview_text("無歷史照片", detail)
            return

        path = Path(str(preview))
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._set_history_preview_text("無法載入歷史照片", f"{detail}｜{path.name}")
            return

        scaled = pixmap.scaled(
            150,
            76,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.history_preview_label.setPixmap(scaled)
        self.history_detail_label.setText(f"{detail}｜{path.name}")

    def _set_history_preview_text(self, title: str, detail: str):
        self.history_preview_label.clear()
        self.history_preview_label.setText(title)
        self.history_detail_label.setText(detail)

    def _refresh_selected_preview(self):
        if not hasattr(self, "selected_preview_table"):
            return
        rows: list[tuple[str, str, str, tuple | None]] = []
        welds = self.co.welds if self.co is not None else []
        for weld in welds:
            spec_text = "/".join(filter(None, [weld.spec.size, weld.spec.sch, weld.spec.material, weld.spec.weld_type]))
            rows.append(("焊口", f"{weld.code or ''}（{_enum_value(weld.op) or ''}）", spec_text or "-", None))
        for index, file in enumerate(self.before_files):
            rows.append(("照片", f"修改前：{Path(file).name}", "可標註", ("before", index, file)))
        for index, file in enumerate(self.after_files):
            rows.append(("照片", f"修改後：{Path(file).name}", "可標註", ("after", index, file)))
        if self.drawing_pdf_file:
            rows.append(("圖面", Path(self.drawing_pdf_file).name, "可標註", ("pdf", None, self.drawing_pdf_file)))
        for material in self.material_requests:
            component = material.get("component") or "未命名材料"
            qty = material.get("qty") or ""
            unit = material.get("unit") or ""
            rows.append(("材料", str(component), f"{qty}{unit}".strip() or "-", None))
        if self.co is not None and self.co.authorization is not None:
            authorization = self.co.authorization
            approved_by = authorization.approved_by or "未填簽認人"
            detail = " / ".join(filter(None, [authorization.approved_at, str(authorization.evidence or "")])) or "-"
            rows.append(("簽認", approved_by, detail, None))

        self.selected_preview_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = row[:3]
            payload = row[3]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0 and payload is not None:
                    item.setData(Qt.ItemDataRole.UserRole, payload)
                self.selected_preview_table.setItem(row_index, col, item)
        self.selected_preview_table.resizeColumnsToContents()
        self.selected_preview_empty_label.setVisible(len(rows) == 0)
        if rows and self.selected_preview_table.currentRow() < 0:
            self.selected_preview_table.selectRow(0)
        self._refresh_selected_preview_detail()

    def _refresh_selected_preview_detail(self):
        if not hasattr(self, "selected_preview_image_label"):
            return
        row = self.selected_preview_table.currentRow()
        if row < 0:
            self._set_preview_detail_text("選擇一筆照片、PDF 或材料", "選取側欄項目後會顯示檔名、狀態與縮圖。")
            return

        type_item = self.selected_preview_table.item(row, 0)
        content_item = self.selected_preview_table.item(row, 1)
        status_item = self.selected_preview_table.item(row, 2)
        kind = type_item.text() if type_item is not None else ""
        content = content_item.text() if content_item is not None else ""
        status = status_item.text() if status_item is not None else ""
        payload = type_item.data(Qt.ItemDataRole.UserRole) if type_item is not None else None

        if payload is None:
            self._set_preview_detail_text(content or kind or "預覽", f"{kind}｜{status}".strip("｜"))
            return

        payload_kind, _index, file = payload
        path = Path(str(file))
        if payload_kind == "pdf":
            self._set_preview_detail_text("PDF", f"{path.name}｜{status}")
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._set_preview_detail_text("無法載入預覽", f"{path.name}｜{status}")
            return

        scaled = pixmap.scaled(
            180,
            100,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.selected_preview_image_label.setPixmap(scaled)
        self.selected_preview_detail_label.setText(f"{content}｜{path.name}｜{status}")

    def _set_preview_detail_text(self, title: str, detail: str):
        self.selected_preview_image_label.clear()
        self.selected_preview_image_label.setText(title)
        self.selected_preview_detail_label.setText(detail)

    def annotate_selected_preview(self):
        payload = self._selected_preview_payload()
        if payload is None:
            self.status_label.setText("請先在已選預覽中選擇照片或 PDF")
            return None

        kind, _index, file = payload
        is_pdf = kind == "pdf"
        path = str(file)
        if not Path(path).exists():
            self.status_label.setText(f"無法標註，檔案不存在：{path}")
            return None

        dialog_cls = self._annotation_dialog_class()
        dialog = dialog_cls(path, is_pdf=is_pdf, parent=self)
        if not getattr(dialog, "_load_ok", True):
            QMessageBox.warning(self, "無法載入", f"無法開啟標註工具：\n{path}")
            return None
        dialog.exec()
        if not getattr(dialog, "was_saved", False):
            return None

        saved_path = str(getattr(dialog, "saved_path", "") or path)
        self._replace_selected_preview_path(payload, saved_path)
        self.status_label.setText(f"已更新標註檔：{Path(saved_path).name}")
        return saved_path

    def _selected_preview_payload(self):
        row = self.selected_preview_table.currentRow()
        if row < 0:
            return None
        item = self.selected_preview_table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _replace_selected_preview_path(self, payload, path: str):
        kind, index, _old_file = payload
        if kind == "before" and isinstance(index, int) and 0 <= index < len(self.before_files):
            self.before_files[index] = path
        elif kind == "after" and isinstance(index, int) and 0 <= index < len(self.after_files):
            self.after_files[index] = path
        elif kind == "pdf":
            self.drawing_pdf_file = path
        self.rebuild_change_order()

    def _annotation_dialog_class(self):
        from gui_annotator import AnnotationDialog

        return AnnotationDialog

    def _refresh_staging(self):
        if not hasattr(self, "staging_table"):
            return
        try:
            files = scan_staging(str(self.staging_root))
        except Exception as exc:
            files = []
            self.staging_empty_label.setText(f"staging 載入失敗：{exc}")
        else:
            self.staging_empty_label.setText("staging/ 目前沒有照片或 PDF")

        self.staging_table.setRowCount(len(files))
        for row_index, staging_file in enumerate(files):
            values = [
                staging_file.filename,
                _file_type_text(staging_file.file_type),
                staging_file.time_label,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, (staging_file.path, staging_file.file_type))
                self.staging_table.setItem(row_index, col, item)
        self.staging_table.resizeColumnsToContents()
        self.staging_empty_label.setVisible(len(files) == 0)

    def _selected_staging_file(self) -> tuple[str, str] | None:
        row = self.staging_table.currentRow()
        if row < 0:
            return None
        item = self.staging_table.item(row, 0)
        if item is None:
            return None
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not payload:
            return None
        path, file_type = payload
        return str(path), str(file_type or "")

    def _add_selected_staging_photo(self, role):
        selected = self._selected_staging_file()
        if selected is None:
            return None
        path, file_type = selected
        if file_type != "image":
            self.status_label.setText("請選擇 staging 裡的照片檔")
            return None
        return self.add_photo_file(role, path)

    def _set_selected_staging_pdf(self):
        selected = self._selected_staging_file()
        if selected is None:
            return None
        path, file_type = selected
        if file_type != "pdf":
            self.status_label.setText("請選擇 staging 裡的 PDF")
            return None
        self.set_drawing_pdf_file(path)
        return path

    def _refresh_attachments_preview(self):
        entries = self._photo_entries()
        self.photo_table.setRowCount(len(entries))
        for row, (role, index) in enumerate(entries):
            file = self.after_files[index] if role == Role.AFTER.value else self.before_files[index]
            for col, value in enumerate([_role_text(role), file]):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.photo_table.setItem(row, col, item)
        self.photo_table.resizeColumnsToContents()
        self.drawing_pdf_label.setText(f"圖面 PDF：{self.drawing_pdf_file or '未選'}")
        self.photo_empty_label.setVisible(len(entries) == 0)

    def _refresh_material_preview(self):
        self.material_table.setRowCount(len(self.material_requests))
        keys = ["component", "size", "schedule", "material", "qty", "unit", "remark"]
        for row, material in enumerate(self.material_requests):
            for col, key in enumerate(keys):
                item = QTableWidgetItem(str(material.get(key) or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.material_table.setItem(row, col, item)
        self.material_table.resizeColumnsToContents()
        self.material_empty_label.setVisible(len(self.material_requests) == 0)

    def _refresh_status(self):
        if self.co is None or self._current_builder is None:
            self.status_label.setText("")
            return
        issues = self._current_builder.validate(self.co, required=self._required_keys())
        status_text = _status_text(self.co.status)
        if issues:
            self.status_label.setText(f"狀態：{status_text} ｜ 還缺：" + "、".join(_issue_text(issue) for issue in issues))
        else:
            self.status_label.setText(f"狀態：{status_text}")

    def _authorization_fields(self) -> dict[str, str | None]:
        if not hasattr(self, "authorization_name_edit"):
            return {"approved_by": None, "approved_at": None, "evidence": None}
        return {
            "approved_by": self.authorization_name_edit.text().strip() or None,
            "approved_at": self.authorization_at_edit.text().strip() or None,
            "evidence": self.authorization_evidence_edit.text().strip() or None,
        }

    def _required_keys(self) -> list[str]:
        if not hasattr(self, "require_materials_checkbox"):
            return []
        keys: list[str] = []
        if self.require_materials_checkbox.isChecked():
            keys.append("materials")
        if self.require_authorization_checkbox.isChecked():
            keys.append("authorization")
        if self.require_reason_checkbox.isChecked():
            keys.append("reason")
        if self.require_welds_checkbox.isChecked():
            keys.append("welds")
        return keys

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
        title = "選擇修改後照片" if _enum_value(role) == Role.AFTER.value else "選擇修改前照片"
        path, _filter = QFileDialog.getOpenFileName(self, title)
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


def _hint(text: str) -> QLabel:
    label = make_hint_label(text)
    label.setWordWrap(True)
    return label


def _status_text(status) -> str:
    return str(_enum_value(status) or "")


def _issue_text(issue: dict) -> str:
    labels = {
        "missing_before_photo": "修改前照片",
        "missing_after_photo": "修改後照片",
        "missing_drawing_pdf": "圖面 PDF",
        "missing_materials": "材料",
        "missing_authorization": "業主簽認",
        "missing_reason": "修改原因",
        "missing_welds": "焊口",
    }
    code = str(issue.get("code") or "")
    return labels.get(code) or str(issue.get("message") or code or "未命名項目")


def _role_text(role) -> str:
    value = _enum_value(role)
    if value == Role.AFTER.value:
        return "修改後"
    if value == Role.BEFORE.value:
        return "修改前"
    return str(value or "")


def _spec_source_text(source) -> str:
    value = _enum_value(source)
    if value == "looked_up":
        return "管制表"
    if value == "manual":
        return "手填"
    return str(value or "")


def _request_kind_text(kind) -> str:
    if kind == "existing":
        return "既有"
    if kind == "new":
        return "新焊口"
    return str(kind or "")


def _file_type_text(file_type) -> str:
    if file_type == "image":
        return "照片"
    if file_type == "pdf":
        return "PDF"
    return str(file_type or "")


def _source_base_for_weld_id(weld_id) -> str:
    text = "" if weld_id is None else str(weld_id).strip()
    body = text[1:] if text.lower().startswith("w") else text
    if len(body) > 1 and body[-1:].isalpha() and body[:-1].isdigit():
        return body[:-1].lstrip("0") or "0"
    if body.isdigit():
        return body.lstrip("0") or "0"
    return text


def _looks_like_date_folder(name: str) -> bool:
    return len(name) == 8 and name.isdigit()


def _split_legacy_folder_name(name: str) -> tuple[str, str]:
    series, sep, suffix = name.partition("_")
    return series, suffix if sep else ""


def _same_series(left, right) -> bool:
    left_text = "" if left is None else str(left).strip()
    right_text = "" if right is None else str(right).strip()
    if left_text.isdigit() and right_text.isdigit():
        return normalize_series_raw(left_text) == normalize_series_raw(right_text)
    return left_text == right_text


def _first_change_order_photo(folder: Path, co: ChangeOrder) -> str:
    for photo in co.photos:
        if not photo.file:
            continue
        raw_path = Path(str(photo.file))
        candidate = raw_path if raw_path.is_absolute() else folder / raw_path
        if candidate.exists() and _is_image_path(candidate):
            return str(candidate)
    return ""


def _first_image_in_folder(folder: Path) -> str:
    try:
        children = sorted(folder.iterdir(), key=lambda path: path.name.lower())
    except OSError:
        return ""
    for path in children:
        if path.is_file() and _is_image_path(path):
            return str(path)
    return ""


def _is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def launch(builder=None, *, records_root=None, attachments_root=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = ChangeOrderWizard(builder=builder, records_root=records_root, attachments_root=attachments_root)
    return dialog.exec()


if __name__ == "__main__":
    raise SystemExit(launch())
