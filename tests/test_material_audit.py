# -*- coding: utf-8 -*-

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from material_audit import append_material_audit, build_material_reprice_event


def test_build_material_reprice_event_records_old_to_new_values():
    event = build_material_reprice_event(
        {
            "項目": 1,
            "報告編號": "R-1",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "單價": "",
            "金額": "",
            "配價狀態": "missing_price",
        },
        {
            "項目": 1,
            "報告編號": "R-1",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "單價": "10",
            "金額": "30",
            "配價狀態": "matched",
            "價目表ID": "pipe-2-sch40-ss",
        },
        operation_id="op",
        actor="tester",
        host="host",
        at="2026-06-16T12:00:00",
    )

    assert event is not None
    assert event["operation_id"] == "op"
    assert event["report_id"] == "R-1"
    assert event["action"] == "repriced"
    assert "pricing" in event["change_types"]
    assert event["changes"]["單價"] == {"old": "", "new": "10"}
    assert event["changes"]["金額"] == {"old": "", "new": "30"}
    assert event["material_key"]["component"] == "Pipe (管)"


def test_append_material_audit_writes_jsonl(tmp_path):
    event = build_material_reprice_event(
        {"報告編號": "R-1", "零件類型": "Pipe (管)", "單價": ""},
        {"報告編號": "R-1", "零件類型": "Pipe (管)", "單價": "10"},
        operation_id="op",
    )

    path, count = append_material_audit(tmp_path, [event])

    assert count == 1
    assert path == tmp_path / "records" / "material_audit.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["changes"]["單價"] == {"old": "", "new": "10"}
