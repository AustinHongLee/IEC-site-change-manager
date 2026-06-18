# -*- coding: utf-8 -*-

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from material_repricing import (
    apply_project_reprice_plan,
    build_reprice_plan,
    format_reprice_summary,
    is_reprice_candidate,
)


def test_reprices_only_unpriced_materials_from_pricebook():
    store = {
        "records": [{
            "報告編號": "R-1",
            "日期": "20260616",
        }],
        "details": [],
        "materials": [{
            "項目": 1,
            "報告編號": "R-1",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "SS",
            "數量": "3",
            "單價": "",
            "金額": "",
            "單價來源": "missing_price",
            "金額來源": "missing_price",
            "配價狀態": "missing_price",
        }],
        "meta": {"version": "2.0"},
    }
    pricebook = {"items": [{
        "id": "pipe-2-sch40-ss",
        "零件類型": "Pipe (管)",
        "尺寸": '2"',
        "SCH": "SCH 40",
        "材質": "白鐵 (Stainless Steel)",
        "單位": "M",
        "單價": "10",
    }]}

    plan = build_reprice_plan(store, pricebook)

    material = plan["store"]["materials"][0]
    assert material["材質"] == "白鐵 (Stainless Steel)"
    assert material["單價"] == "10"
    assert material["金額"] == "30"
    assert material["單位"] == "M"
    assert material["單價來源"] == "pricebook"
    assert material["配價狀態"] == "matched"
    assert plan["summary"]["candidates"] == 1
    assert plan["summary"]["matched"] == 1
    assert plan["summary"]["updated"] == 1
    assert plan["summary"]["affected_reports"] == 1
    assert plan["affected_report_ids"] == ["R-1"]
    assert plan["audit_events"]
    assert plan["store"]["records"][0]["需重產"] == "1"
    assert plan["store"]["records"][0]["需重產原因"] == "材料補價後金額變更"


def test_reprice_plan_skips_locked_report_ids():
    store = {
        "records": [],
        "details": [],
        "materials": [{
            "報告編號": "R-1",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "數量": "1",
            "單價": "",
            "單價來源": "missing_price",
        }],
    }
    pricebook = {"items": [{
        "零件類型": "Pipe (管)",
        "尺寸": '2"',
        "SCH": "SCH 40",
        "材質": "白鐵 (Stainless Steel)",
        "單價": "10",
        "單位": "M",
    }]}

    plan = build_reprice_plan(store, pricebook, locked_report_ids={"R-1"})

    assert plan["store"]["materials"][0]["單價"] == ""
    assert plan["summary"]["candidates"] == 0
    assert plan["summary"]["skipped_locked"] == 1


def test_manual_price_or_amount_is_not_reprice_candidate():
    assert not is_reprice_candidate({
        "零件類型": "Pipe (管)",
        "單價": "",
        "單價來源": "manual",
    })
    assert not is_reprice_candidate({
        "零件類型": "Pipe (管)",
        "單價": "",
        "金額來源": "manual",
    })


def test_reprice_summary_mentions_key_counts():
    text = format_reprice_summary({
        "total_materials": 3,
        "candidates": 2,
        "matched": 1,
        "missing_price": 1,
        "missing_pricebook": 0,
        "skipped_locked": 1,
        "skipped_manual": 0,
        "affected_reports": 1,
    })

    assert "待重配未定價: 2" in text
    assert "可套用補價: 1" in text
    assert "受影響修改單: 1" in text
    assert "已請款略過: 1" in text


def test_apply_project_reprice_plan_appends_material_audit(tmp_path, monkeypatch):
    import material_repricing
    import record_manager

    records_dir = tmp_path / "records"
    records_dir.mkdir()
    records_path = records_dir / "records.json"
    records_path.write_text(
        json.dumps({
            "records": [{"報告編號": "R-1"}],
            "details": [],
            "materials": [{
                "項目": 1,
                "報告編號": "R-1",
                "零件類型": "Pipe (管)",
                "尺寸": '2"',
                "SCH": "SCH 40",
                "材質": "白鐵 (Stainless Steel)",
                "數量": "2",
                "單價": "",
                "金額": "",
                "單價來源": "missing_price",
                "配價狀態": "missing_price",
            }],
            "meta": {"version": "2.0"},
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(record_manager, "RECORDS_JSON_PATH", str(records_path))
    monkeypatch.setattr(material_repricing.record_manager, "RECORDS_JSON_PATH", str(records_path))

    store = json.loads(records_path.read_text(encoding="utf-8"))
    plan = build_reprice_plan(store, {"items": [{
        "零件類型": "Pipe (管)",
        "尺寸": '2"',
        "SCH": "SCH 40",
        "材質": "白鐵 (Stainless Steel)",
        "單價": "10",
        "單位": "M",
    }]})

    apply_project_reprice_plan(plan)

    audit_path = records_dir / "material_audit.jsonl"
    assert audit_path.exists()
    line = audit_path.read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(line)["report_id"] == "R-1"
    updated = json.loads(records_path.read_text(encoding="utf-8"))
    assert updated["materials"][0]["單價"] == "10"
    assert updated["records"][0]["需重產"] == "1"
