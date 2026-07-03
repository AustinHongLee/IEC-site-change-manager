# -*- coding: utf-8 -*-
"""請款面板中不需建立 QApplication 的邏輯測試。"""

import os
import sys

import pytest

pytest.importorskip("PyQt6")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from gui_panels import BillingPanel, MaterialPricebookPanel, RecordManagerPanel


def test_total_amount_is_never_saved_as_manual_override():
    row = {"total": "999", "total_source": "manual"}

    assert BillingPanel._billing_amount_for_save(row, "total") == ""


def test_calculated_amounts_are_not_saved_as_manual_values():
    row = {"weld_amount": "100", "weld_amount_source": "calculated"}

    assert BillingPanel._billing_amount_for_save(row, "weld_amount") == ""


def test_manual_section_amounts_are_preserved():
    row = {"material_amount": "250", "material_amount_source": "manual"}

    assert BillingPanel._billing_amount_for_save(row, "material_amount") == "250"


def test_format_amount_uses_billing_rounding():
    assert BillingPanel._format_amount("100.5") == "$101"


def test_missing_price_hint_is_not_saved_as_material_value():
    assert RecordManagerPanel._normalize_material_edit_value("未配價") == ""
    assert RecordManagerPanel._normalize_material_edit_value("未定價") == ""


def test_pricebook_seed_import_confirmation_mentions_no_overwrite():
    message = MaterialPricebookPanel._format_import_seed_confirmation(
        "material_pricebook_seed.json",
        {
            "items": [],
            "added": [{"id": "new"}],
            "skipped": [{"id": "existing"}],
            "existing_count": 1,
            "candidate_count": 2,
        },
        [],
    )

    assert "將新增: 1" in message
    assert "已存在略過: 1" in message
    assert "既有項目不會被覆蓋" in message


def test_pricebook_import_validation_message_lists_errors():
    class Report:
        errors = ["第 1 列：零件類型 不可空白"]
        warnings = []

    message = MaterialPricebookPanel._format_import_validation_message(Report())

    assert "ERROR: 1" in message
    assert "零件類型 不可空白" in message


def test_pricebook_unpriced_item_detection_requires_component_and_blank_price():
    assert MaterialPricebookPanel._is_unpriced_item({"零件類型": "Pipe (管)", "單價": ""})
    assert not MaterialPricebookPanel._is_unpriced_item({"零件類型": "Pipe (管)", "單價": "10"})
    assert not MaterialPricebookPanel._is_unpriced_item({"零件類型": "", "單價": ""})


def test_pricebook_batch_fill_updates_selected_rows_only():
    panel = type("Panel", (), {})()
    panel.items = [
        {"零件類型": "Pipe (管)", "單價": "", "來源": "", "生效日": ""},
        {"零件類型": "Valve (閥)", "單價": "", "來源": "", "生效日": ""},
    ]

    MaterialPricebookPanel._apply_batch_price(panel, [0], "120", "合約", "2026-06-16")

    assert panel.items[0]["單價"] == "120"
    assert panel.items[0]["來源"] == "合約"
    assert panel.items[0]["生效日"] == "2026-06-16"
    assert panel.items[1]["單價"] == ""


def test_pricebook_batch_fill_confirmation_mentions_save_required():
    panel = type("Panel", (), {})()
    panel.items = [{
        "零件類型": "Pipe (管)",
        "尺寸": '2"',
        "SCH": "SCH 40",
        "材質": "白鐵 (Stainless Steel)",
    }]

    message = MaterialPricebookPanel._format_batch_fill_price_confirmation(
        panel,
        [0],
        "120",
        "合約",
        "2026-06-16",
    )

    assert "批次填價 1 筆" in message
    assert "Pipe (管)" in message
    assert "尚需按「儲存」" in message


def test_pricebook_filters_can_combine_component_material_and_unpriced():
    item = {
        "零件類型": "Pipe (管)",
        "材質": "白鐵 (Stainless Steel)",
        "尺寸": '2"',
        "單價": "",
    }

    assert MaterialPricebookPanel._matches_pricebook_filters(
        item,
        keyword="2",
        component_filter="Pipe (管)",
        material_filter="白鐵 (Stainless Steel)",
        only_unpriced=True,
    )
    assert not MaterialPricebookPanel._matches_pricebook_filters(
        item,
        keyword="2",
        component_filter="Valve (閥)",
        material_filter="白鐵 (Stainless Steel)",
        only_unpriced=True,
    )
    assert not MaterialPricebookPanel._matches_pricebook_filters(
        {**item, "單價": "120"},
        keyword="",
        component_filter="全部零件",
        material_filter="全部材質",
        only_unpriced=True,
    )


def test_pricebook_filter_active_detects_dropdown_filters():
    assert MaterialPricebookPanel._pricebook_filter_active("", "Pipe (管)", "全部材質", False)
    assert MaterialPricebookPanel._pricebook_filter_active("", "全部零件", "白鐵 (Stainless Steel)", False)
    assert not MaterialPricebookPanel._pricebook_filter_active("", "全部零件", "全部材質", False)


def test_reprice_confirmation_mentions_locked_and_manual_protection():
    message = MaterialPricebookPanel._format_reprice_message({
        "total_materials": 3,
        "candidates": 2,
        "matched": 1,
        "missing_price": 1,
        "missing_pricebook": 0,
        "skipped_locked": 1,
        "skipped_manual": 1,
    }, apply=True, affected_report_ids=["R-1"])

    assert "可套用補價: 1" in message
    assert "手動價" in message
    assert "已請款" in message
    assert "不會被覆蓋" in message
    assert "R-1" in message
    assert "需重產" in message


def test_record_manager_material_warning_uses_action_language():
    message = RecordManagerPanel._format_material_warning({
        "total": 3,
        "missing_price": 2,
        "missing_pricebook": 1,
    })
    tooltip = RecordManagerPanel._format_material_warning_tooltip({
        "total": 3,
        "missing_price": 2,
        "missing_pricebook": 1,
    })

    assert message == "待補價 2、待建料 1"
    assert "未定價（待補價）：2 筆" in tooltip
    assert "查無價目（待建料）：1 筆" in tooltip


def test_record_manager_rebuild_tooltip_mentions_regeneration():
    tooltip = RecordManagerPanel._format_rebuild_tooltip({
        "rebuild_reason": "材料補價後金額變更",
        "rebuild_at": "2026-06-16T12:00:00",
    })

    assert "重新產出" in tooltip
    assert "材料補價後金額變更" in tooltip


def test_record_manager_rebuild_queue_export_message_mentions_count_and_path():
    message = RecordManagerPanel._format_rebuild_queue_export_message(
        [{"報告編號": "R-1"}, {"報告編號": "R-2"}],
        "C:/tmp/rebuild.csv",
    )

    assert "2 張" in message
    assert "C:/tmp/rebuild.csv" in message


def test_record_manager_output_center_confirmation_mentions_safe_output():
    message = RecordManagerPanel._format_output_center_export_confirmation(
        "C:/project/staging/site_output_center_gui",
        "目前篩選結果 (2)",
        2,
        "照片 PDF",
    )

    assert "attachments/" in message
    assert "原始 attachments/ 不會被修改" in message
    assert "site_output_center_gui" in message
    assert "目前篩選結果 (2)" in message
    assert "預計修改單：2 張" in message
    assert "輸出內容：照片 PDF" in message


def test_record_manager_output_center_content_label_lists_selected_outputs():
    assert RecordManagerPanel._format_output_center_content_label({
        "statistics_xlsx": True,
        "summary_pdf": False,
        "photo_grid_pdf": True,
    }) == "現場統計單 Excel、照片 PDF"
    assert RecordManagerPanel._format_output_center_content_label({
        "statistics_xlsx": False,
        "summary_pdf": False,
        "photo_grid_pdf": False,
    }) == "未選擇"

    assert RecordManagerPanel._format_output_center_selected_content_label("owner-data", {
        "statistics_xlsx": True,
        "summary_pdf": True,
        "photo_grid_pdf": True,
    }) == "業主資料包（資料夾 + 索引 Excel）"
    assert RecordManagerPanel._format_output_center_selected_content_label("both", {
        "statistics_xlsx": True,
        "summary_pdf": False,
        "photo_grid_pdf": True,
    }) == "業主資料包（資料夾 + 索引 Excel）、現場統計單 Excel、照片 PDF"


def test_record_manager_output_center_output_dir_normalization_uses_default():
    default_dir = "C:/project/staging/site_output_center_gui"

    assert RecordManagerPanel._normalize_output_center_output_dir("", default_dir).endswith(
        "site_output_center_gui"
    )
    assert RecordManagerPanel._normalize_output_center_output_dir('"C:/tmp/output_center"', default_dir) == os.path.abspath("C:/tmp/output_center")


def test_record_manager_output_center_output_items_list_user_artifacts(tmp_path):
    report_set = tmp_path / "real_canonical_report_set.json"
    stats = tmp_path / "real_site_statistics.xlsx"
    summary = tmp_path / "output_center_summary.json"
    photo_pdf = tmp_path / "real_photo_grid_0547_AG.pdf"
    for path in (report_set, stats, summary, photo_pdf):
        path.write_text("x", encoding="utf-8")

    items = RecordManagerPanel._output_center_output_items({
        "files": {
            "report_set": str(report_set),
            "statistics_xlsx": str(stats),
            "summary": str(summary),
        },
        "renders": [
            {
                "template": "photo_grid",
                "folder": "0547_AG",
                "pages": 1,
                "path": str(photo_pdf),
            },
            {
                "template": "summary",
                "folder": "55_2a2",
                "pages": 0,
                "path": "",
            },
        ],
    })

    kinds = [item["kind"] for item in items]
    assert kinds == ["資料 JSON", "現場統計單 Excel", "摘要 JSON", "照片 PDF"]
    assert items[-1]["report"] == "0547_AG"
    assert items[-1]["pages"] == "1"
    assert all(item["exists"] for item in items)


def test_record_manager_output_center_groups_outputs_and_warnings(tmp_path):
    report_set = tmp_path / "canonical_report_set.json"
    stats = tmp_path / "site_statistics.xlsx"
    summary = tmp_path / "output_center_summary.json"
    photo_pdf = tmp_path / "site_photo_grid_0547_AG.pdf"
    for path in (report_set, stats, summary, photo_pdf):
        path.write_text("x", encoding="utf-8")

    groups = RecordManagerPanel._output_center_output_groups({
        "files": {
            "report_set": str(report_set),
            "statistics_xlsx": str(stats),
            "summary": str(summary),
        },
        "renders": [
            {
                "template": "photo_grid",
                "folder": "0547_AG",
                "ok": True,
                "pages": 1,
                "path": str(photo_pdf),
            },
            {
                "template": "summary",
                "folder": "55_2a2",
                "ok": False,
                "pages": 0,
                "path": "",
                "issue_codes": ["field_missing"],
            },
        ],
        "issues": [{"report": "0547_AG", "code": "note", "message": "缺少現場 note"}],
    })

    assert [group["title"] for group in groups] == ["主要輸出", "PDF", "資料檔", "資料提醒"]
    assert groups[0]["items"][0]["kind"] == "現場統計單 Excel"
    assert groups[1]["status"] == "2 項，1 項需注意"
    assert groups[1]["items"][0]["status"] == "OK，1 頁"
    assert groups[1]["items"][1]["status"] == "失敗：field_missing"
    assert groups[3]["items"][0]["message"] == "缺少現場 note"
    assert groups[3]["items"][0]["record_ref"] == {
        "report": "0547_AG",
        "report_id": "",
        "date": "",
        "folder": "0547_AG",
    }
    assert groups[3]["items"][0]["issue_action"]["label"] == "編輯 note.txt"


def test_record_manager_output_center_record_ref_matching():
    record = {
        "report_id": "R-001",
        "date": "20260112",
        "folder": "0547_AG",
    }

    assert RecordManagerPanel._record_matches_output_ref(record, {"report_id": "R-001"})
    assert RecordManagerPanel._record_matches_output_ref(record, {"date": "20260112", "folder": "0547_AG"})
    assert RecordManagerPanel._record_matches_output_ref(record, {"report": "0547_AG"})
    assert RecordManagerPanel._record_matches_output_ref(record, {"folder": "0547_AG"})
    assert not RecordManagerPanel._record_matches_output_ref(record, {"date": "20260113", "folder": "0547_AG"})


def test_record_manager_output_center_issue_ref_prefers_locator_fields():
    ref = RecordManagerPanel._output_center_issue_record_ref({
        "report": "R-001",
        "report_id": "R-001",
        "date": "20260112",
        "folder": "0547_AG",
    })

    assert ref == {
        "report": "R-001",
        "report_id": "R-001",
        "date": "20260112",
        "folder": "0547_AG",
    }
    assert RecordManagerPanel._format_output_center_record_ref_label(ref) == "R-001"


def test_record_manager_output_center_filter_reset_helpers():
    assert RecordManagerPanel._output_center_filters_are_narrowed("需重產") is True
    assert RecordManagerPanel._output_center_filters_are_narrowed("全部", "0547") is True
    assert RecordManagerPanel._output_center_filters_are_narrowed("全部", "", "20260101") is True
    assert RecordManagerPanel._output_center_filters_are_narrowed("全部", "", "", "") is False

    message = RecordManagerPanel._format_output_center_focus_missing_message(
        {"date": "20260112", "folder": "0547_AG"},
        filters_reset=True,
    )
    assert "已切回全部狀態並清空搜尋" in message
    assert "20260112/0547_AG" in message


def test_record_manager_output_center_filter_reset_clears_widgets():
    class FakeCombo:
        def __init__(self):
            self.value = "需重產"
            self.signals_blocked = False

        def currentText(self):
            return self.value

        def findText(self, text):
            return 0 if text == "全部" else -1

        def blockSignals(self, value):
            old = self.signals_blocked
            self.signals_blocked = value
            return old

        def setCurrentIndex(self, _idx):
            self.value = "全部"

    class FakeEdit:
        def __init__(self, value):
            self.value = value

        def text(self):
            return self.value

        def clear(self):
            self.value = ""

    class FakePanel:
        _output_center_filters_are_narrowed = staticmethod(RecordManagerPanel._output_center_filters_are_narrowed)

        def __init__(self):
            self.status_combo = FakeCombo()
            self.search_edit = FakeEdit("0547")
            self.date_from_edit = FakeEdit("20260101")
            self.date_to_edit = FakeEdit("20260131")
            self.loaded = False

        def load_records(self):
            self.loaded = True

    panel = FakePanel()

    assert RecordManagerPanel._reset_record_filters_for_output_focus(panel) is True
    assert panel.status_combo.currentText() == "全部"
    assert panel.search_edit.text() == ""
    assert panel.date_from_edit.text() == ""
    assert panel.date_to_edit.text() == ""
    assert panel.loaded is True


def test_record_manager_output_center_issue_actions_by_code():
    cases = {
        "note": ("edit_note", "編輯 note.txt"),
        "before_photo": ("add_photo", "新增 before 照片"),
        "after_photo": ("add_photo", "新增 after 照片"),
        "parse_error": ("open_folder", "開啟資料夾檢查文字檔"),
        "weld_or_material": ("focus_record", "定位修改單檢查焊口/材料"),
        "unknown": ("focus_record", "定位修改單"),
    }

    for code, (kind, label) in cases.items():
        action = RecordManagerPanel._output_center_issue_action({"code": code})
        assert action["kind"] == kind
        assert action["label"] == label

    tooltip = RecordManagerPanel._format_output_center_issue_tooltip(
        "缺少現場 note",
        RecordManagerPanel._output_center_issue_action({"code": "note"}),
    )
    assert "缺少現場 note" in tooltip
    assert "處理：編輯 note.txt" in tooltip


def test_record_manager_output_center_photo_action_prefixes_and_paths(tmp_path):
    before_action = RecordManagerPanel._output_center_issue_action({"code": "before_photo"})
    after_action = RecordManagerPanel._output_center_issue_action({"code": "after_photo"})

    assert before_action["kind"] == "add_photo"
    assert before_action["prefix"] == "before"
    assert after_action["kind"] == "add_photo"
    assert after_action["prefix"] == "after"
    assert RecordManagerPanel._normalize_output_center_photo_prefix("修改前") == "before"
    assert RecordManagerPanel._normalize_output_center_photo_prefix("修改後") == "after"

    assert RecordManagerPanel._next_output_center_photo_path(str(tmp_path), "before") == str(tmp_path / "before.jpg")
    (tmp_path / "before.jpg").write_text("x", encoding="utf-8")
    assert RecordManagerPanel._next_output_center_photo_path(str(tmp_path), "before") == str(tmp_path / "before_1.jpg")
    (tmp_path / "before_1.jpg").write_text("x", encoding="utf-8")
    assert RecordManagerPanel._next_output_center_photo_path(str(tmp_path), "before") == str(tmp_path / "before_2.jpg")
    assert RecordManagerPanel._next_output_center_photo_path(str(tmp_path), "side") == ""


def test_record_manager_output_center_note_text_helpers(tmp_path):
    note_path = tmp_path / "note.txt"

    assert RecordManagerPanel._output_center_note_text_is_valid("") is False
    assert RecordManagerPanel._output_center_note_text_is_valid("# 請填寫修改原因說明") is False
    assert RecordManagerPanel._output_center_note_text_is_valid("請填寫現場說明") is False
    assert RecordManagerPanel._output_center_note_text_is_valid("現場加長修改，補焊口照片") is True

    RecordManagerPanel._write_output_center_note_text(str(note_path), "現場加長修改")

    assert RecordManagerPanel._read_output_center_note_text(str(note_path)) == "現場加長修改\n"


def test_record_manager_output_center_report_keys_skip_archived_and_deduplicate():
    keys = RecordManagerPanel._output_center_report_keys([
        {"date": "20260112", "folder": "0547_AG", "is_archived": False},
        {"date": "20260112", "folder": "0547_AG", "is_archived": False},
        {"date": "20250820", "folder": "55_2a2", "is_archived": True},
        {"date": "", "folder": "bad", "is_archived": False},
    ])

    assert keys == [("20260112", "0547_AG")]


def test_record_manager_output_center_scope_options_include_available_scopes():
    options = RecordManagerPanel._output_center_scope_options(
        selected_count=1,
        visible_count=2,
        total_count=3,
    )

    assert [item["mode"] for item in options] == ["all", "visible", "selected"]
    assert "3" in options[0]["label"]
    assert "2" in options[1]["label"]
    assert "1" in options[2]["label"]


def test_record_manager_output_center_export_message_summarizes_outputs():
    message = RecordManagerPanel._format_output_center_export_message({
        "ok": True,
        "output_center": "C:/project/staging/site_output_center_gui",
        "report_count": 2,
        "aggregates": {
            "weld_count": 8,
            "material_row_count": 3,
            "photo_count": 6,
        },
        "files": {"statistics_xlsx": "C:/project/output/real_site_statistics.xlsx"},
        "renders": [
            {"template": "summary", "ok": True, "path": "C:/project/output/a.pdf"},
            {"template": "photo_grid", "ok": True, "path": "C:/project/output/b.pdf"},
            {"template": "photo_grid", "ok": True, "path": "C:/project/output/c.pdf"},
        ],
        "issues": [{"report": "0547_AG", "message": "缺少現場 note"}],
    })

    assert "現場輸出中心已產出" in message
    assert "修改單：2 張" in message
    assert "焊口：8 口" in message
    assert "照片：6 張" in message
    assert "照片 PDF 2 份" in message
    assert "統計 PDF 1 份" in message
    assert "site_output_center_gui" in message
    assert "缺少現場 note" in message


def test_billing_unresolved_material_blocks_batch_creation_message():
    message = BillingPanel._format_unresolved_material_blocks({
        "R-1": {"total": "3", "missing_price": "2", "missing_pricebook": "1"},
    })
    tooltip = BillingPanel._format_unresolved_material_tooltip({
        "unresolved_material_total": "3",
        "missing_price_count": "2",
        "missing_pricebook_count": "1",
    })

    assert "暫不允許加入請款批次" in message
    assert "R-1" in message
    assert "待補價 2" in message
    assert "待建料 1" in message
    assert "尚未可請款" in tooltip


def test_batch_selection_report_ids_are_deduplicated():
    assert BillingPanel._unique_report_ids_from_values(["R-1", "", "R-2", "R-1"]) == ["R-1", "R-2"]


def test_batch_conflict_message_mentions_existing_batch():
    message = BillingPanel._format_batch_conflicts({"R-1": "B-001"})

    assert "R-1" in message
    assert "B-001" in message
    assert "不能重複加入" in message


def test_batch_create_confirmation_mentions_locking():
    message = BillingPanel._format_batch_create_confirmation(["R-1", "R-2"], "2026-06", "業主A")

    assert "共 2 張修改單" in message
    assert "2026-06" in message
    assert "業主A" in message
    assert "避免重複請款" in message


def test_batch_created_message_summarizes_batch():
    message = BillingPanel._format_batch_created_message({
        "batch_id": "B-001",
        "status": "草稿",
        "period": "2026-06",
        "client": "業主A",
        "items": [{"report_id": "R-1"}, {"report_id": "R-2"}],
    })

    assert "B-001" in message
    assert "修改單數量：2" in message
    assert "業主A" in message


def test_batch_status_confirmation_does_not_imply_record_status_change():
    message = BillingPanel._format_batch_status_confirmation({
        "batch_id": "B-001",
        "status": "草稿",
        "period": "2026-06",
        "client": "業主A",
        "items": [{"report_id": "R-1"}],
    }, "請款中")

    assert "草稿 → 請款中" in message
    assert "修改單數量：1" in message
    assert "不會自動修改各修改單的請款狀態" in message


def test_batch_detail_tooltip_lists_report_ids():
    tooltip = BillingPanel._format_batch_detail_tooltip({
        "batch_id": "B-001",
        "status": "請款中",
        "period": "2026-06",
        "client": "業主A",
        "items": [{"report_id": "R-1"}, {"report_id": "R-2"}],
    })

    assert "B-001" in tooltip
    assert "請款中" in tooltip
    assert "R-1" in tooltip
    assert "R-2" in tooltip


def test_billing_confirmation_mentions_sensitive_changes():
    events = [{
        "report_id": "R-1",
        "change_types": ["amount", "status"],
        "changes": {
            "status": {"old": "未請款", "new": "請款中"},
            "weld_amount": {"old": "100", "new": "120"},
            "remark": {"old": "", "new": "送出"},
        },
    }]

    message = BillingPanel._format_billing_confirmation(events)

    assert "R-1" in message
    assert "狀態 未請款 → 請款中" in message
    assert "焊口金額 100 → 120" in message
    assert "備註" not in message


def test_status_issue_message_includes_report_context():
    from billing_status import BillingStatusIssue

    message = BillingPanel._format_status_issues([
        BillingStatusIssue(
            report_id="R-1",
            old_status="未請款",
            new_status="已請款",
            message="請款狀態不可由「未請款」直接改為「已請款」",
        )
    ])

    assert "R-1" in message
    assert "不可由「未請款」直接改為「已請款」" in message
