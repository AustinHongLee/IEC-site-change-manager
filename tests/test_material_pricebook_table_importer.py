# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from material_pricebook_table_importer import (
    build_price_table_import_plan,
    load_and_plan_price_table_import,
    load_price_table_items,
    validate_price_table_items,
)


def test_csv_price_table_updates_blank_price_and_adds_new_item(tmp_path):
    csv_path = tmp_path / "price_table.csv"
    csv_path.write_text(
        "\n".join([
            "零件類型,尺寸,SCH,材質,單位,單價,來源,生效日",
            'Pipe (管),2",SCH 40,SS,M,"$1,200",合約,2026/06/01',
            'Elbow (彎頭),2",SCH 40,白鐵 (Stainless Steel),個,80,報價,2026-06-02',
        ]),
        encoding="utf-8-sig",
    )
    target_path = tmp_path / "material_pricebook.json"
    current = {
        "items": [{
            "id": "existing-pipe",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "單位": "M",
            "單價": "",
        }]
    }

    _items, report, plan, _current = load_and_plan_price_table_import(
        str(csv_path),
        target_path=str(target_path),
    )
    plan = build_price_table_import_plan(load_price_table_items(str(csv_path)), current)

    assert report.ok
    assert len(plan["updated"]) == 1
    assert len(plan["added"]) == 1
    assert plan["updated"][0]["after"]["id"] == "existing-pipe"
    assert plan["updated"][0]["after"]["單價"] == "1200"
    assert plan["updated"][0]["after"]["來源"] == "合約"
    assert plan["updated"][0]["after"]["生效日"] == "2026-06-01"
    assert plan["added"][0]["零件類型"] == "Elbow (彎頭)"
    assert plan["added"][0]["單價"] == "80"


def test_existing_priced_item_conflict_is_skipped_without_overwrite():
    current = {
        "items": [{
            "id": "pipe-2-ss",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "SS",
            "單位": "M",
            "單價": "100",
        }]
    }
    incoming = [{
        "零件類型": "Pipe (管)",
        "尺寸": '2"',
        "SCH": "SCH 40",
        "材質": "白鐵 (Stainless Steel)",
        "單位": "M",
        "單價": "120",
    }]

    report = validate_price_table_items(incoming)
    plan = build_price_table_import_plan(incoming, current)

    assert report.ok
    assert len(plan["conflicts"]) == 1
    assert not plan["updated"]
    assert plan["items"][0]["單價"] == "100"


def test_invalid_price_blocks_price_table_plan(tmp_path):
    csv_path = tmp_path / "bad_price.csv"
    csv_path.write_text(
        "\n".join([
            "零件類型,尺寸,SCH,材質,單位,單價",
            'Pipe (管),2",SCH 40,SS,M,abc',
        ]),
        encoding="utf-8",
    )

    _items, report, plan, _current = load_and_plan_price_table_import(str(csv_path))

    assert not report.ok
    assert any("不是合法數字" in msg for msg in report.errors)
    assert not plan["added"]
    assert not plan["updated"]


def test_xlsx_price_table_loads_when_openpyxl_available(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = Path(tmp_path) / "price_table.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["零件類型", "尺寸", "SCH", "材質", "單位", "單價", "來源"])
    ws.append(["Valve (閥)", '1"', "SCH 40", "CS", "個", 300, "合約"])
    wb.save(path)

    items = load_price_table_items(str(path))
    report = validate_price_table_items(items)

    assert report.ok
    assert items[0]["零件類型"] == "Valve (閥)"
    assert items[0]["單價"] == "300"
