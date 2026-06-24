# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime

import pytest
from openpyxl import Workbook


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

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


def test_change_order_wizard_source_driven_slice_smoke(qapp, tmp_path):
    records_root = tmp_path / "records"
    dialog = ChangeOrderWizard(builder=_builder_for_fixture(tmp_path), records_root=records_root)
    try:
        dialog.series_edit.setText("088")
        dialog.date_edit.setText("20260624")
        dialog.reason_edit.setPlainText("現場管線干涉")
        dialog.rebuild_change_order()

        assert dialog.co.series == "88"
        assert dialog.co.dwg_no == "DWG-88"

        _set_combo_text(dialog.existing_op_combo, Op.EXTEND.value)
        dialog.existing_base_edit.setText("2")
        first_existing = dialog.add_existing_request()
        dialog.existing_base_edit.setText("2")
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

        saved_path = dialog.save_draft()
        loaded = ChangeOrder.load_json(saved_path)

        assert saved_path == records_root / "88_20260624_01" / "change_order.json"
        assert saved_path.exists()
        assert loaded.id == "88_20260624_01"
        assert loaded.series == "88"
        assert loaded.status == Status.PARTIAL
        assert loaded.reason == "現場管線干涉"
        assert [w.code for w in loaded.welds] == ["2b", "2c", "1001"]
    finally:
        dialog.close()
        dialog.deleteLater()
