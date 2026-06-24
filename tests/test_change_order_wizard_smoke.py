# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime

import pytest
from openpyxl import Workbook
from PIL import Image


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from PyQt6.QtWidgets import QApplication, QTabWidget  # noqa: E402

from change_order import ChangeOrder, Op, SpecSource, Status  # noqa: E402
from change_order_builder import ChangeOrderBuilder  # noqa: E402
from change_order_wizard import ChangeOrderWizard  # noqa: E402
from weld_control import WeldControlManager  # noqa: E402
from weld_lookup import WeldLookup  # noqa: E402


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FixtureLookup(WeldLookup):
    def lookup_dwg_no(self, series):
        rows = self.manager.get_all_welds_by_serial(str(series).lstrip("0") or "0")
        return rows[0].get("圖號") if rows else None


def _fixed_clock():
    return datetime(2026, 6, 24, 8, 30, 5)


def _write_weld_control_fixture(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "焊口編號明細"
    ws.append(["流水號", "銲口編號", "尺寸", "厚度", "材質", "銲接型式", "屬性.1", "圖號"])
    ws.append([88, "2", '2"', "SCH40", "SUS304", "BW", "焊口", "DWG-88"])
    ws.append([88, "2a", '2"', "SCH40", "SUS304", "BW", "焊口", "DWG-88"])
    ws.append([88, "9", '3"', "SCH10", "SUS316", "RF", "VALVE安裝", "DWG-88"])
    wb.save(path)
    wb.close()


def _builder_for_fixture(tmp_path):
    workbook = tmp_path / "weld_control.xlsx"
    _write_weld_control_fixture(workbook)
    manager = WeldControlManager({
        "file_path": str(workbook),
        "sheet_name": "焊口編號明細",
        "col_serial": "流水號",
        "col_weld_no": "焊口編號",
    })
    return ChangeOrderBuilder(lookup=FixtureLookup(manager=manager), clock=_fixed_clock)


def _set_combo_text(combo, text):
    index = combo.findText(text)
    assert index >= 0
    combo.setCurrentIndex(index)


def test_change_order_wizard_source_driven_slice_smoke(qapp, tmp_path, monkeypatch):
    attachments_root = tmp_path / "records"
    before_path = tmp_path / "before.jpg"
    annotated_before_path = tmp_path / "before-annotated.jpg"
    after_path = tmp_path / "after.JPG"
    drawing_path = tmp_path / "drawing-source.pdf"
    staging_root = tmp_path / "staging"
    staging_root.mkdir()
    legacy_folder = attachments_root / "20260620" / "088_OLD"
    legacy_folder.mkdir(parents=True)
    Image.new("RGB", (18, 12), (180, 90, 50)).save(legacy_folder / "before.jpg", format="JPEG")
    staging_before = staging_root / "stage-before.jpg"
    staging_pdf = staging_root / "stage-drawing.pdf"
    before_path.write_bytes(b"before")
    annotated_before_path.write_bytes(b"annotated-before")
    Image.new("RGB", (16, 10), (80, 160, 90)).save(after_path, format="JPEG")
    drawing_path.write_bytes(b"%PDF")
    staging_before.write_bytes(b"stage-before")
    staging_pdf.write_bytes(b"%PDF-stage")

    dialog = ChangeOrderWizard(builder=_builder_for_fixture(tmp_path), attachments_root=attachments_root)
    try:
        assert dialog.splitter.count() == 2
        assert not dialog.sidebar.isHidden()
        dialog.toggle_sidebar()
        assert dialog.sidebar.isHidden()
        dialog.toggle_sidebar()
        assert not dialog.sidebar.isHidden()

        tabs = dialog.findChild(QTabWidget)
        assert tabs is not None
        assert [tabs.tabText(index) for index in range(tabs.count())] == [
            "① 基本資料",
            "② 焊口",
            "③ 照片與圖面",
            "④ 材料",
        ]
        assert dialog.weld_table.horizontalHeaderItem(0).text() == "焊口碼"
        assert dialog.photo_table.horizontalHeaderItem(0).text() == "角色"
        assert dialog.material_table.horizontalHeaderItem(0).text() == "零件"
        assert dialog.staging_table.rowCount() == 2
        assert {
            dialog.staging_table.item(row, 0).text()
            for row in range(dialog.staging_table.rowCount())
        } == {"stage-before.jpg", "stage-drawing.pdf"}

        dialog.series_edit.setText("088")
        dialog.date_edit.setText("20260624")
        dialog.reason_edit.setPlainText("現場管線干涉")
        dialog.rebuild_change_order()

        assert dialog.co.series == "88"
        assert dialog.co.dwg_no == "DWG-88"
        assert dialog.source_weld_table.horizontalHeaderItem(0).text() == "現有焊口"
        assert dialog.source_weld_table.rowCount() == 2
        assert dialog.source_weld_table.item(0, 0).text() == "2"
        assert dialog.source_weld_table.item(0, 1).text() == "2"
        assert dialog.source_weld_table.item(1, 0).text() == "2a"
        assert dialog.source_weld_table.item(1, 1).text() == "2"
        assert dialog.history_table.rowCount() == 1
        assert dialog.history_table.item(0, 0).text() == "088_OLD"
        assert dialog.history_table.item(0, 3).text() == "舊資料"
        history_pixmap = dialog.history_preview_label.pixmap()
        assert history_pixmap is not None
        assert not history_pixmap.isNull()
        assert "088_OLD" in dialog.history_detail_label.text()
        opened_paths = []
        monkeypatch.setattr(dialog, "_open_path", lambda path: opened_paths.append(str(path)))
        dialog.history_table.selectRow(0)
        assert dialog.open_selected_history_folder() == str(legacy_folder)
        assert opened_paths[-1] == str(legacy_folder)
        assert dialog.open_staging_folder() == str(staging_root)
        assert opened_paths[-1] == str(staging_root)

        _set_combo_text(dialog.existing_op_combo, Op.EXTEND.value)
        dialog.source_weld_table.selectRow(0)
        assert dialog.existing_base_edit.text() == "2"
        first_existing = dialog.add_existing_request()
        dialog.source_weld_table.selectRow(1)
        assert dialog.existing_base_edit.text() == "2"
        second_existing = dialog.add_existing_request()

        assert first_existing.code == "2b"
        assert first_existing.spec.size == '2"'
        assert first_existing.spec_source == SpecSource.LOOKED_UP
        assert second_existing.code == "2c"

        _set_combo_text(dialog.new_op_combo, Op.EXTEND.value)
        dialog.new_size_edit.setText('1"')
        dialog.new_sch_edit.setText("SCH40")
        dialog.new_material_edit.setText("SUS304")
        dialog.new_weld_type_edit.setText("BW")
        first_new = dialog.add_new_request()

        dialog.new_size_edit.setText('3"')
        dialog.new_sch_edit.setText("SCH80")
        dialog.new_material_edit.setText("CS")
        dialog.new_weld_type_edit.setText("SW")
        second_new = dialog.add_new_request()

        assert first_new.code == "1001"
        assert second_new.code == "1002"
        assert [w.code for w in dialog.co.welds] == ["2b", "2c", "1001", "1002"]

        dialog.weld_table.selectRow(2)
        dialog.remove_selected_request()

        assert [w.code for w in dialog.co.welds] == ["2b", "2c", "1001"]
        assert dialog.weld_table.item(2, 0).text() == "1001"

        assert dialog.create_final() is None
        assert dialog.co.status == Status.PARTIAL
        assert "正式建立被擋" in dialog.status_label.text()
        assert "修改前照片" in dialog.status_label.text()
        assert "修改後照片" in dialog.status_label.text()
        assert "圖面 PDF" in dialog.status_label.text()

        dialog.add_photo_file("before", before_path)
        dialog.add_photo_file("after", after_path)
        dialog.set_drawing_pdf_file(drawing_path)
        dialog.material_component_edit.setText("Pipe")
        dialog.material_size_edit.setText('2"')
        dialog.material_sch_edit.setText("SCH40")
        dialog.material_material_edit.setText("SUS304")
        dialog.material_qty_edit.setText("2")
        dialog.material_unit_edit.setText("M")
        dialog.material_remark_edit.setText("現場補料")
        dialog.add_material_request()

        dialog.rebuild_change_order()
        assert dialog.co.status == Status.COMPLETE
        assert dialog.status_label.text() == "狀態：完整"
        assert dialog.selected_preview_table.rowCount() >= 6
        for row in range(dialog.selected_preview_table.rowCount()):
            if "修改後" in dialog.selected_preview_table.item(row, 1).text():
                dialog.selected_preview_table.selectRow(row)
                break
        pixmap = dialog.selected_preview_image_label.pixmap()
        assert pixmap is not None
        assert not pixmap.isNull()
        assert "after.JPG" in dialog.selected_preview_detail_label.text()

        dialog.require_authorization_checkbox.setChecked(True)
        dialog.rebuild_change_order()
        assert dialog.co.status == Status.PARTIAL
        assert "業主簽認" in dialog.status_label.text()
        assert dialog.create_final() is None
        assert "業主簽認" in dialog.status_label.text()

        dialog.authorization_name_edit.setText("王主任")
        dialog.authorization_at_edit.setText("20260624")
        dialog.authorization_evidence_edit.setText("現場簽認照片")
        dialog.rebuild_change_order()
        assert dialog.co.status == Status.COMPLETE
        assert dialog.status_label.text() == "狀態：完整"
        assert any(
            dialog.selected_preview_table.item(row, 0).text() == "簽認"
            for row in range(dialog.selected_preview_table.rowCount())
        )

        class FakeAnnotationDialog:
            def __init__(self, path, is_pdf=False, parent=None):
                self.path = path
                self.is_pdf = is_pdf
                self.parent = parent
                self.was_saved = False
                self.saved_path = ""
                self._load_ok = True

            def exec(self):
                self.was_saved = True
                self.saved_path = str(annotated_before_path)
                return 1

        monkeypatch.setattr(dialog, "_annotation_dialog_class", lambda: FakeAnnotationDialog)
        for row in range(dialog.selected_preview_table.rowCount()):
            if "修改前" in dialog.selected_preview_table.item(row, 1).text():
                dialog.selected_preview_table.selectRow(row)
                break
        assert dialog.annotate_selected_preview() == str(annotated_before_path)
        assert dialog.before_files[0] == str(annotated_before_path)
        assert "已更新標註檔" in dialog.status_label.text()

        for row in range(dialog.staging_table.rowCount()):
            if dialog.staging_table.item(row, 0).text() == "stage-before.jpg":
                dialog.staging_table.selectRow(row)
                break
        assert dialog._add_selected_staging_photo("before") == str(staging_before)
        assert str(staging_before) in dialog.before_files

        for row in range(dialog.staging_table.rowCount()):
            if dialog.staging_table.item(row, 0).text() == "stage-drawing.pdf":
                dialog.staging_table.selectRow(row)
                break
        assert dialog._set_selected_staging_pdf() == str(staging_pdf)
        assert dialog.drawing_pdf_file == str(staging_pdf)
        dialog.before_files.remove(str(staging_before))
        dialog.set_drawing_pdf_file(drawing_path)

        saved_path = dialog.save_draft()
        loaded = ChangeOrder.load_json(saved_path)

        assert saved_path == attachments_root / "88_20260624_01" / "change_order.json"
        assert saved_path.exists()
        assert (saved_path.parent / "before_1.jpg").read_bytes() == b"annotated-before"
        assert (saved_path.parent / "after_1.JPG").read_bytes() == after_path.read_bytes()
        assert (saved_path.parent / "drawing.pdf").read_bytes() == b"%PDF"
        assert loaded.id == "88_20260624_01"
        assert loaded.series == "88"
        assert loaded.status == Status.COMPLETE
        assert loaded.reason == "現場管線干涉"
        assert [w.code for w in loaded.welds] == ["2b", "2c", "1001"]
        assert [photo.file for photo in loaded.photos] == ["before_1.jpg", "after_1.JPG"]
        assert loaded.drawing_pdf.file == "drawing.pdf"
        assert len(loaded.materials) == 1
        assert loaded.materials[0].component == "Pipe"
        assert loaded.materials[0].schedule == "SCH40"
        assert loaded.materials[0].remark == "現場補料"
        assert loaded.authorization.approved_by == "王主任"
        assert loaded.authorization.evidence == "現場簽認照片"
        assert dialog.history_table.rowCount() == 2
        assert dialog.history_table.item(0, 0).text() == "88_20260624_01"
        assert dialog.history_table.item(1, 0).text() == "088_OLD"

        second_path = dialog.create_final()
        second_loaded = ChangeOrder.load_json(second_path)
        assert second_path == attachments_root / "88_20260624_02" / "change_order.json"
        assert second_loaded.status == Status.COMPLETE
        assert dialog.history_table.rowCount() == 3
    finally:
        dialog.close()
        dialog.deleteLater()
