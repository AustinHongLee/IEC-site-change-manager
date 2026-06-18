# -*- coding: utf-8 -*-
"""material_pricebook.py 單元測試"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from material_pricebook import (
    apply_material_pricing,
    find_material_price,
    load_material_pricebook,
    save_material_pricebook,
    unresolved_material_counts_by_report,
    unresolved_material_price_status,
)


def test_find_material_price_prefers_more_specific_match():
    pricebook = {
        "items": [
            {"id": "pipe-generic", "零件類型": "Pipe", "單價": "10"},
            {"id": "pipe-2-ss", "零件類型": "Pipe", "尺寸": "2", "材質": "SS", "單價": "25"},
        ]
    }

    match = find_material_price({"零件類型": "Pipe", "尺寸": "2", "材質": "SS"}, pricebook)

    assert match is not None
    assert match.source_id == "pipe-2-ss"


def test_find_material_price_treats_blank_pricebook_fields_as_wildcards():
    pricebook = {"items": [{"id": "elbow-any", "零件類型": "Elbow", "單價": "50"}]}

    match = find_material_price({"零件類型": "Elbow", "尺寸": "4", "材質": "CS"}, pricebook)

    assert match is not None
    assert match.source_id == "elbow-any"


def test_apply_material_pricing_sets_price_amount_and_source():
    rows = [{
        "零件類型": "Tee",
        "尺寸": "3",
        "材質": "SS",
        "數量": "2",
        "單位": "個",
    }]
    pricebook = {
        "items": [{
            "id": "tee-3-ss",
            "零件類型": "Tee",
            "尺寸": "3",
            "材質": "SS",
            "類別": "耗材",
            "單價": "120",
            "來源": "合約",
            "生效日": "2026-01-01",
        }]
    }

    priced = apply_material_pricing(rows, pricebook)

    assert priced[0]["單價"] == "120"
    assert priced[0]["金額"] == "240"
    assert priced[0]["類別"] == "耗材"
    assert priced[0]["單價來源"] == "pricebook"
    assert priced[0]["價目表ID"] == "tee-3-ss"
    assert priced[0]["價目來源"] == "合約"
    assert priced[0]["價目生效日"] == "2026-01-01"


def test_apply_material_pricing_matches_material_alias_to_canonical_pricebook():
    rows = [{
        "零件類型": "Pipe (管)",
        "尺寸": '2"',
        "SCH": "SCH 40",
        "材質": "白鐵",
        "數量": "3",
    }]
    pricebook = {
        "items": [{
            "id": "pipe-2-sch40-ss",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "單價": "10",
            "單位": "M",
        }]
    }

    priced = apply_material_pricing(rows, pricebook)

    assert priced[0]["材質"] == "白鐵 (Stainless Steel)"
    assert priced[0]["單價"] == "10"
    assert priced[0]["金額"] == "30"
    assert priced[0]["單位"] == "M"
    assert priced[0]["配價狀態"] == "matched"


def test_apply_material_pricing_marks_known_item_without_price_as_missing_price():
    rows = [{
        "零件類型": "Pipe (管)",
        "尺寸": '2"',
        "SCH": "SCH 40",
        "材質": "SS",
        "數量": "3",
    }]
    pricebook = {
        "items": [{
            "id": "pipe-2-sch40-ss",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "單價": "",
            "單位": "M",
        }]
    }

    priced = apply_material_pricing(rows, pricebook)

    assert priced[0]["材質"] == "白鐵 (Stainless Steel)"
    assert priced[0]["單位"] == "M"
    assert priced[0]["單價"] == ""
    assert priced[0]["金額"] == ""
    assert priced[0]["單價來源"] == "missing_price"
    assert priced[0]["金額來源"] == "missing_price"
    assert priced[0]["價目表ID"] == "pipe-2-sch40-ss"
    assert priced[0]["配價狀態"] == "missing_price"


def test_apply_material_pricing_preserves_manual_price():
    rows = [{
        "零件類型": "Tee",
        "數量": "2",
        "單價": "99",
    }]
    pricebook = {"items": [{"id": "tee", "零件類型": "Tee", "單價": "120"}]}

    priced = apply_material_pricing(rows, pricebook)

    assert priced[0]["單價"] == "99"
    assert priced[0]["金額"] == "198"
    assert priced[0]["單價來源"] == "manual"


def test_apply_material_pricing_marks_missing_pricebook_match():
    rows = [{
        "零件類型": "Reducer",
        "尺寸": "6x4",
        "材質": "SS",
        "數量": "1",
    }]
    pricebook = {"items": [{"id": "pipe", "零件類型": "Pipe", "單價": "100"}]}

    priced = apply_material_pricing(rows, pricebook)

    assert priced[0]["單價"] == ""
    assert priced[0]["金額"] == ""
    assert priced[0]["單價來源"] == "missing_pricebook"
    assert priced[0]["金額來源"] == "missing_price"
    assert priced[0]["配價狀態"] == "missing_pricebook"


def test_unresolved_material_counts_by_report_splits_missing_price_states():
    rows = [
        {"報告編號": "R-1", "零件類型": "Pipe (管)", "單價": "", "單價來源": "missing_price"},
        {"報告編號": "R-1", "零件類型": "Valve (閥)", "單價": "", "配價狀態": "missing_pricebook"},
        {"報告編號": "R-1", "零件類型": "Pipe (管)", "單價": "10", "配價狀態": "matched"},
        {"報告編號": "R-2", "零件類型": "", "單價": "", "配價狀態": "missing_price"},
    ]

    counts = unresolved_material_counts_by_report(rows)

    assert unresolved_material_price_status(rows[0]) == "missing_price"
    assert counts["R-1"]["total"] == 2
    assert counts["R-1"]["missing_price"] == 1
    assert counts["R-1"]["missing_pricebook"] == 1
    assert "R-2" not in counts


def test_save_and_load_material_pricebook_normalizes_items(tmp_path):
    path = tmp_path / "material_pricebook.json"

    save_material_pricebook({
        "items": [{
            "component": "Pipe",
            "size": "2",
            "material": "SS",
            "unit_price": "$1,200",
        }]
    }, str(path))

    data = load_material_pricebook(str(path))

    assert data["items"][0]["零件類型"] == "Pipe"
    assert data["items"][0]["尺寸"] == "2"
    assert data["items"][0]["材質"] == "白鐵 (Stainless Steel)"
    assert data["items"][0]["類別"] == "材料"
    assert data["items"][0]["單價"] == "1200"
    assert data["items"][0]["來源"] == "合約"
    assert data["items"][0]["單位"] == "個"
    assert data["items"][0]["id"] == "Pipe|2|白鐵 (Stainless Steel)"
    assert json.loads(path.read_text(encoding="utf-8"))["meta"]["currency"] == "TWD"


def test_normalize_pricebook_items_defaults_known_component_unit():
    data = {
        "items": [{
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "CS",
            "單價": "",
        }]
    }

    priced = apply_material_pricing([{
        "零件類型": "Pipe (管)",
        "尺寸": '2"',
        "SCH": "SCH 40",
        "材質": "黑鐵",
        "數量": "1",
    }], data)

    assert priced[0]["單位"] == "M"
    assert priced[0]["價目表ID"] == 'Pipe (管)|2"|SCH 40|黑鐵 (Carbon Steel)'


def test_save_material_pricebook_appends_price_change_history(tmp_path):
    path = tmp_path / "material_pricebook.json"

    save_material_pricebook({
        "items": [{
            "id": "pipe-2-ss",
            "零件類型": "Pipe",
            "尺寸": "2",
            "材質": "SS",
            "類別": "材料",
            "單價": "100",
            "來源": "合約",
            "生效日": "2026-01-01",
        }]
    }, str(path))

    save_material_pricebook({
        "items": [{
            "id": "pipe-2-ss",
            "零件類型": "Pipe",
            "尺寸": "2",
            "材質": "SS",
            "類別": "材料",
            "單價": "120",
            "來源": "報價",
            "生效日": "2026-02-01",
        }]
    }, str(path))

    data = load_material_pricebook(str(path))

    assert data["meta"]["version"] == "1.1"
    assert len(data["history"]) == 1
    event = data["history"][0]
    assert event["event"] == "price_changed"
    assert event["id"] == "pipe-2-ss"
    assert event["類別"] == "材料"
    assert event["old_price"] == "100"
    assert event["new_price"] == "120"
    assert event["old_source"] == "合約"
    assert event["new_source"] == "報價"
    assert event["old_effective_date"] == "2026-01-01"
    assert event["new_effective_date"] == "2026-02-01"
