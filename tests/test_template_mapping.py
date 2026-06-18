# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from template_mapping import is_valid_field_path, resolve_field_path, validate_template_mapping


def _report():
    return {
        "report": {
            "report_id": "R-1",
            "date": "2026-06-17",
            "description": "現場修改",
        },
        "welds": {
            "rows": [
                {"code": "1r2", "size": 2, "mark": "r"},
                {"code": "2r2", "size": 2, "mark": "r"},
            ],
            "count": 2,
        },
        "materials": {
            "rows": [{"component": "Pipe (管)", "qty": 3, "unit": "M"}],
            "count": 1,
        },
        "photos": {
            "before": [{"path": "C:/p/before.jpg", "name": "before.jpg"}],
            "after": [{"path": "C:/p/after.jpg", "name": "after.jpg"}],
            "mode": "single",
        },
    }


def test_resolve_field_path_supports_scalar_index_and_wildcard():
    report = _report()

    assert resolve_field_path(report, "report.report_id") == "R-1"
    assert resolve_field_path(report, "photos.before[0].path") == "C:/p/before.jpg"
    assert resolve_field_path(report, "photos.before[0..n].path") == ["C:/p/before.jpg"]
    assert resolve_field_path(report, "welds.rows[*].code") == ["1r2", "2r2"]
    assert resolve_field_path(report, "materials.rows") == [{"component": "Pipe (管)", "qty": 3, "unit": "M"}]
    assert resolve_field_path(report, "photos.before[9].path") == ""


def test_template_mapping_accepts_three_core_primitives():
    template = {
        "template_id": "sample",
        "schema_version": "template_mapping.v1",
        "kind": "xlsx_template",
        "fields": [
            {"type": "text", "source": "report.report_id", "cell": "A1"},
            {"type": "image", "source": "photos.before[0].path", "anchor": "B2"},
            {
                "type": "table",
                "source": "welds.rows",
                "start_cell": "A10",
                "max_rows": 10,
                "columns": [{"source": "code"}, {"source": "size"}],
            },
        ],
    }

    result = validate_template_mapping(template)

    assert result["ok"] is True
    assert result["errors"] == []


def test_template_mapping_rejects_unknown_paths_and_bad_table_columns():
    template = {
        "fields": [
            {"type": "text", "source": "report.not_a_field"},
            {"type": "image", "source": "photos.before[*].path"},
            {"type": "table", "source": "materials.rows", "columns": [{"source": "not_a_column"}]},
        ]
    }

    result = validate_template_mapping(template)

    assert result["ok"] is False
    assert any("report.not_a_field" in error for error in result["errors"])
    assert any("不可使用 [*]" in error for error in result["errors"])
    assert any("not_a_column" in error for error in result["errors"])


def test_template_mapping_requires_table_row_limit():
    template = {
        "fields": [
            {"type": "table", "source": "materials.rows", "columns": [{"source": "component"}]},
        ]
    }

    result = validate_template_mapping(template)

    assert result["ok"] is False
    assert any("max_rows" in error for error in result["errors"])


def test_is_valid_field_path_accepts_numeric_photo_index_from_catalog_family():
    assert is_valid_field_path("photos.after[0].path") is True
    assert is_valid_field_path("photos.after[0]") is True
    assert is_valid_field_path("photos.after[0..n]") is True


def test_photo_wildcard_root_can_be_used_as_table_source():
    template = {
        "fields": [
            {
                "type": "table",
                "source": "photos.before[*]",
                "max_rows": 5,
                "columns": ["name", "path"],
            },
        ]
    }

    result = validate_template_mapping(template)

    assert result["ok"] is True
    assert result["errors"] == []
