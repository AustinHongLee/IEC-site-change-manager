# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from pdf_overlay_schema import validate_pdf_overlay_template
from template_mapping import validate_template_mapping


def _valid_template():
    return {
        "template_id": "vendor_pdf",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "kind": "pdf_overlay",
        "base_pdf": "vendor.pdf",
        "coordinate_space": "normalized",
        "fields": [
            {
                "type": "text",
                "source": "report.report_id",
                "page": 1,
                "rect_norm": [0.08, 0.08, 0.24, 0.04],
                "font_size": 10,
                "min_font_size": 7,
                "overflow": "shrink",
            },
            {
                "type": "image",
                "source": "photos.before[0].path",
                "page": 1,
                "rect_norm": [0.08, 0.20, 0.36, 0.25],
                "fit": "contain",
            },
            {
                "type": "table",
                "source": "materials.rows",
                "page": 1,
                "rect_norm": [0.08, 0.52, 0.84, 0.30],
                "rows_per_page": 8,
                "overflow": "new_page",
                "columns": [
                    {"source": "component", "width_norm": 0.5},
                    {"source": "qty", "width_norm": 0.25},
                    {"source": "unit", "width_norm": 0.25},
                ],
            },
        ],
    }


def test_pdf_overlay_schema_accepts_normalized_targets():
    result = validate_pdf_overlay_template(_valid_template())

    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_template_mapping_accepts_pdf_overlay_source_and_target_schema():
    result = validate_template_mapping(_valid_template())

    assert result["ok"] is True
    assert result["target_validation"]["schema_version"] == "pdf_overlay.v1"


def test_pdf_overlay_schema_rejects_excel_target_fields_and_missing_rect():
    template = _valid_template()
    template["fields"][0]["cell"] = "A1"
    del template["fields"][1]["rect_norm"]

    result = validate_template_mapping(template)

    assert result["ok"] is False
    assert any("Excel 落點欄位" in error for error in result["errors"])
    assert any("rect_norm" in error for error in result["errors"])


def test_pdf_overlay_schema_rejects_out_of_bounds_and_overlap():
    template = _valid_template()
    template["fields"][0]["rect_norm"] = [0.9, 0.08, 0.2, 0.04]
    template["fields"][1]["rect_norm"] = [0.08, 0.52, 0.20, 0.10]

    result = validate_pdf_overlay_template(template)

    assert result["ok"] is False
    assert any("0..1" in error for error in result["errors"])
    assert any("重疊" in error for error in result["errors"])


def test_pdf_overlay_schema_rejects_table_column_width_overflow():
    template = _valid_template()
    template["fields"][2]["columns"][0]["width_norm"] = 0.8
    template["fields"][2]["columns"][1]["width_norm"] = 0.4

    result = validate_pdf_overlay_template(template)

    assert result["ok"] is False
    assert any("width_norm" in error for error in result["errors"])


def test_pdf_overlay_schema_rejects_invalid_table_header_height():
    template = _valid_template()
    template["fields"][2]["header_height_pt"] = 0

    result = validate_pdf_overlay_template(template)

    assert result["ok"] is False
    assert any("header_height_pt" in error for error in result["errors"])


def test_pdf_overlay_schema_validates_table_image_columns():
    template = _valid_template()
    template["fields"][2]["source"] = "photos.before[*]"
    template["fields"][2]["columns"] = [
        {"source": "path", "cell_type": "image", "fit": "contain", "width_norm": 0.7},
        {"source": "name", "cell_type": "text", "width_norm": 0.3},
    ]

    assert validate_template_mapping(template)["ok"] is True

    template["fields"][2]["columns"][0]["cell_type"] = "photo"
    template["fields"][2]["columns"][0]["fit"] = "inside"

    result = validate_pdf_overlay_template(template)

    assert result["ok"] is False
    assert any("cell_type" in error for error in result["errors"])
    assert any("fit" in error for error in result["errors"])
