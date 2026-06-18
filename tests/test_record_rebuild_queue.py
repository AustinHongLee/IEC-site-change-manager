# -*- coding: utf-8 -*-

import csv
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from record_rebuild_queue import (
    build_rebuild_queue,
    export_rebuild_queue_csv,
    format_rebuild_queue_summary,
)


def test_build_rebuild_queue_includes_reason_time_and_material_blocks():
    store = {
        "records": [
            {
                "報告編號": "R-1",
                "日期": "20260616",
                "Series NO": "001",
                "資料夾名": "001_1A",
                "焊口清單": "1A",
                "變更類型": "新增",
                "說明": "材料補價",
                "需重產": "1",
                "需重產原因": "材料補價後金額變更",
                "需重產時間": "2026-06-16T12:00:00",
            },
            {
                "報告編號": "R-2",
                "需重產": "",
            },
        ],
        "materials": [
            {
                "報告編號": "R-1",
                "零件類型": "Pipe (管)",
                "單價": "",
                "單價來源": "missing_price",
            },
            {
                "報告編號": "R-1",
                "零件類型": "Valve (閥)",
                "單價": "",
                "配價狀態": "missing_pricebook",
            },
        ],
    }

    rows = build_rebuild_queue(store)

    assert len(rows) == 1
    assert rows[0]["報告編號"] == "R-1"
    assert rows[0]["需重產原因"] == "材料補價後金額變更"
    assert rows[0]["待補價"] == "1"
    assert rows[0]["待建料"] == "1"
    assert "R-1" in format_rebuild_queue_summary(rows)


def test_export_rebuild_queue_csv_writes_utf8_sig(tmp_path):
    path = tmp_path / "rebuild_queue.csv"
    rows = [{
        "報告編號": "R-1",
        "日期": "20260616",
        "需重產原因": "材料補價後金額變更",
    }]

    export_rebuild_queue_csv(str(path), rows)

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        loaded = list(csv.DictReader(f))
    assert loaded[0]["報告編號"] == "R-1"
    assert loaded[0]["需重產原因"] == "材料補價後金額變更"
