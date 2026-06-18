# -*- coding: utf-8 -*-

import csv
import os
import sys
from pathlib import Path

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from material_pricebook_template_exporter import (
    PRICE_TABLE_TEMPLATE_HEADERS,
    build_price_table_template_items,
    export_price_table_template,
)
from material_pricebook_table_importer import load_price_table_items


def _items():
    return [
        {
            "id": "pipe-empty",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "SS",
            "單位": "M",
            "單價": "",
        },
        {
            "id": "valve-priced",
            "零件類型": "Valve (閥)",
            "材質": "CS",
            "單位": "個",
            "單價": "300",
        },
    ]


def test_build_template_items_defaults_to_unpriced_only():
    rows = build_price_table_template_items(_items())

    assert len(rows) == 1
    assert rows[0]["id"] == "pipe-empty"
    assert rows[0]["材質"] == "白鐵 (Stainless Steel)"
    assert rows[0]["單價"] == ""


def test_export_template_csv_roundtrips_to_price_table_importer(tmp_path):
    path = tmp_path / "template.csv"

    result = export_price_table_template(str(path), _items())

    assert result["count"] == 1
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
    assert headers == PRICE_TABLE_TEMPLATE_HEADERS

    imported = load_price_table_items(str(path))
    assert imported[0]["id"] == "pipe-empty"
    assert imported[0]["單價"] == ""


def test_export_template_xlsx_when_openpyxl_available(tmp_path):
    pytest.importorskip("openpyxl")
    path = Path(tmp_path) / "template.xlsx"

    result = export_price_table_template(str(path), _items(), only_unpriced=False)
    imported = load_price_table_items(str(path))

    assert result["count"] == 2
    assert len(imported) == 2
    assert imported[1]["id"] == "valve-priced"
    assert imported[1]["單價"] == "300"
