# -*- coding: utf-8 -*-
"""
test_record_manager.py — record_manager.py 的單元測試

測試涵蓋：
- auto_backup 功能
"""

import os
import sys
import time
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))


class TestAutoBackup:
    """自動備份測試"""

    def test_backup_creates_file(self, tmp_path):
        from record_manager import auto_backup

        # 建立假的 Excel 檔
        fake_xlsx = tmp_path / "test.xlsx"
        fake_xlsx.write_bytes(b"fake excel content")

        result = auto_backup(str(fake_xlsx), max_backups=3)
        assert result != ""
        assert os.path.exists(result)

    def test_backup_max_limit(self, tmp_path):
        from record_manager import auto_backup

        fake_xlsx = tmp_path / "test.xlsx"
        fake_xlsx.write_bytes(b"fake excel content")

        # 建立 5 個備份
        for _ in range(5):
            auto_backup(str(fake_xlsx), max_backups=3)
            time.sleep(0.01)  # 確保時間戳不同

        backup_dir = tmp_path / "backups"
        backups = [f for f in os.listdir(str(backup_dir)) if f.endswith(".xlsx")]
        assert len(backups) <= 3

    def test_backup_nonexistent_file(self, tmp_path):
        from record_manager import auto_backup

        result = auto_backup(str(tmp_path / "nonexistent.xlsx"))
        assert result == ""


class TestUpsertRecord:
    """主紀錄 upsert 測試"""

    def test_successful_upsert_clears_rebuild_flag(self, tmp_path, monkeypatch):
        import record_manager

        records_path = tmp_path / "records.json"
        records_path.write_text(
            json.dumps({
                "records": [{
                    "報告編號": "R-1",
                    "日期": "20260616",
                    "資料夾名": "001_1A",
                    "需重產": "1",
                    "需重產原因": "材料補價後金額變更",
                    "需重產時間": "2026-06-16T12:00:00",
                }],
                "details": [],
                "materials": [],
                "meta": {"version": "2.0"},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(record_manager, "RECORDS_JSON_PATH", str(records_path))

        record_manager.upsert_record([{
            "報告編號": "R-1",
            "日期": "20260616",
            "資料夾名": "001_1A",
            "說明": "重新產出完成",
        }])

        data = json.loads(records_path.read_text(encoding="utf-8"))
        rec = data["records"][0]
        assert rec["說明"] == "重新產出完成"
        assert "需重產" not in rec
        assert "需重產原因" not in rec
        assert "需重產時間" not in rec


class TestUpsertMaterialsRows:
    """材料明細 upsert 測試"""

    def test_preserves_existing_manual_price_when_pricebook_row_arrives(self, tmp_path, monkeypatch):
        import record_manager

        records_path = tmp_path / "records.json"
        records_path.write_text(
            json.dumps({
                "records": [],
                "details": [],
                "materials": [{
                    "項目": 1,
                    "報告編號": "R-1",
                    "零件類型": "Pipe",
                    "尺寸": "2",
                    "材質": "SS",
                    "數量": "1",
                    "單位": "個",
                    "單價": "500",
                    "金額": "500",
                    "單價來源": "manual",
                    "金額來源": "calculated",
                }],
                "meta": {"version": "2.0"},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(record_manager, "RECORDS_JSON_PATH", str(records_path))

        record_manager.upsert_materials_rows([{
            "報告編號": "R-1",
            "零件類型": "Pipe",
            "尺寸": "2",
            "材質": "SS",
            "數量": "2",
            "單位": "個",
            "單價": "100",
            "金額": "200",
            "單價來源": "pricebook",
            "金額來源": "calculated",
            "價目表ID": "pipe-2-ss",
        }])

        data = json.loads(records_path.read_text(encoding="utf-8"))
        mat = data["materials"][0]
        assert mat["數量"] == "2"
        assert mat["單價"] == "500"
        assert mat["金額"] == "1000"
        assert mat["單價來源"] == "manual"

    def test_material_key_includes_sch(self, tmp_path, monkeypatch):
        import record_manager

        records_path = tmp_path / "records.json"
        billing_path = tmp_path / "billing.json"
        records_path.write_text(
            json.dumps({
                "records": [],
                "details": [],
                "materials": [],
                "meta": {"version": "2.0"},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        billing_path.write_text('{"billing": {}}', encoding="utf-8")
        monkeypatch.setattr(record_manager, "RECORDS_JSON_PATH", str(records_path))
        monkeypatch.setattr(record_manager, "BILLING_JSON_PATH", str(billing_path))

        record_manager.upsert_materials_rows([
            {
                "報告編號": "R-1",
                "零件類型": "Pipe",
                "尺寸": "2",
                "SCH": "40",
                "材質": "SS",
                "數量": "1",
            },
            {
                "報告編號": "R-1",
                "零件類型": "Pipe",
                "尺寸": "2",
                "SCH": "80",
                "材質": "SS",
                "數量": "1",
            },
        ])

        data = json.loads(records_path.read_text(encoding="utf-8"))
        assert len(data["materials"]) == 2
        assert {m["SCH"] for m in data["materials"]} == {"40", "80"}

    def test_locked_billing_status_freezes_existing_and_new_material_rows(self, tmp_path, monkeypatch):
        import record_manager

        records_path = tmp_path / "records.json"
        billing_path = tmp_path / "billing.json"
        records_path.write_text(
            json.dumps({
                "records": [],
                "details": [],
                "materials": [{
                    "項目": 1,
                    "報告編號": "R-1",
                    "零件類型": "Pipe",
                    "尺寸": "2",
                    "SCH": "40",
                    "材質": "SS",
                    "類別": "材料",
                    "數量": "1",
                    "單價": "",
                    "金額": "",
                }],
                "meta": {"version": "2.0"},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        billing_path.write_text(
            json.dumps({"billing": {"R-1": {"status": "已請款"}}}, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(record_manager, "RECORDS_JSON_PATH", str(records_path))
        monkeypatch.setattr(record_manager, "BILLING_JSON_PATH", str(billing_path))

        record_manager.upsert_materials_rows([
            {
                "報告編號": "R-1",
                "零件類型": "Pipe",
                "尺寸": "2",
                "SCH": "40",
                "材質": "SS",
                "數量": "2",
                "單價": "100",
                "金額": "200",
                "單價來源": "pricebook",
            },
            {
                "報告編號": "R-1",
                "零件類型": "Elbow",
                "尺寸": "2",
                "SCH": "40",
                "材質": "SS",
                "數量": "1",
                "單價": "50",
            },
        ])

        data = json.loads(records_path.read_text(encoding="utf-8"))
        assert len(data["materials"]) == 1
        mat = data["materials"][0]
        assert mat["數量"] == "1"
        assert mat["單價"] == ""
        assert mat["金額"] == ""

    def test_missing_pricebook_match_does_not_overwrite_existing_price(self, tmp_path, monkeypatch):
        import record_manager

        records_path = tmp_path / "records.json"
        billing_path = tmp_path / "billing.json"
        records_path.write_text(
            json.dumps({
                "records": [],
                "details": [],
                "materials": [{
                    "項目": 1,
                    "報告編號": "R-1",
                    "零件類型": "Pipe",
                    "尺寸": "2",
                    "SCH": "40",
                    "材質": "SS",
                    "數量": "1",
                    "單價": "100",
                    "金額": "100",
                    "單價來源": "pricebook",
                    "金額來源": "calculated",
                    "價目表ID": "pipe-2-40-ss",
                    "價目來源": "合約",
                    "價目生效日": "2026-01-01",
                    "配價狀態": "matched",
                }],
                "meta": {"version": "2.0"},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        billing_path.write_text('{"billing": {}}', encoding="utf-8")
        monkeypatch.setattr(record_manager, "RECORDS_JSON_PATH", str(records_path))
        monkeypatch.setattr(record_manager, "BILLING_JSON_PATH", str(billing_path))

        record_manager.upsert_materials_rows([{
            "報告編號": "R-1",
            "零件類型": "Pipe",
            "尺寸": "2",
            "SCH": "40",
            "材質": "SS",
            "類別": "材料",
            "數量": "1",
            "單價": "",
            "金額": "",
            "單價來源": "missing_pricebook",
            "金額來源": "missing_price",
            "價目表ID": "",
            "價目來源": "",
            "價目生效日": "",
            "配價狀態": "missing_pricebook",
        }])

        data = json.loads(records_path.read_text(encoding="utf-8"))
        mat = data["materials"][0]
        assert mat["單價"] == "100"
        assert mat["金額"] == "100"
        assert mat["類別"] == "材料"
        assert mat["單價來源"] == "pricebook"
        assert mat["金額來源"] == "calculated"
        assert mat["價目表ID"] == "pipe-2-40-ss"
        assert mat["價目來源"] == "合約"
        assert mat["價目生效日"] == "2026-01-01"
        assert mat["配價狀態"] == "matched"

    def test_missing_unit_price_does_not_overwrite_existing_price(self, tmp_path, monkeypatch):
        import record_manager

        records_path = tmp_path / "records.json"
        billing_path = tmp_path / "billing.json"
        records_path.write_text(
            json.dumps({
                "records": [],
                "details": [],
                "materials": [{
                    "項目": 1,
                    "報告編號": "R-1",
                    "零件類型": "Pipe (管)",
                    "尺寸": "2\"",
                    "SCH": "40",
                    "材質": "白鐵 (Stainless Steel)",
                    "數量": "1",
                    "單價": "100",
                    "金額": "100",
                    "單價來源": "pricebook",
                    "金額來源": "calculated",
                    "價目表ID": "pipe-2-40-ss",
                    "配價狀態": "matched",
                }],
                "meta": {"version": "2.0"},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        billing_path.write_text('{"billing": {}}', encoding="utf-8")
        monkeypatch.setattr(record_manager, "RECORDS_JSON_PATH", str(records_path))
        monkeypatch.setattr(record_manager, "BILLING_JSON_PATH", str(billing_path))

        record_manager.upsert_materials_rows([{
            "報告編號": "R-1",
            "零件類型": "Pipe (管)",
            "尺寸": "2\"",
            "SCH": "40",
            "材質": "白鐵 (Stainless Steel)",
            "數量": "1",
            "單價": "",
            "金額": "",
            "單價來源": "missing_price",
            "金額來源": "missing_price",
            "價目表ID": "pipe-2-40-ss",
            "配價狀態": "missing_price",
        }])

        data = json.loads(records_path.read_text(encoding="utf-8"))
        mat = data["materials"][0]
        assert mat["單價"] == "100"
        assert mat["金額"] == "100"
        assert mat["單價來源"] == "pricebook"
        assert mat["配價狀態"] == "matched"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
