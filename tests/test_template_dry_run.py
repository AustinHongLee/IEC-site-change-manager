# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from template_dry_run import dry_run_template_for_report, dry_run_template_for_report_set


def _report(image_path: str = ""):
    return {
        "report": {
            "report_id": "R-1",
            "folder": "001_1r2",
            "description": "現場修改",
        },
        "welds": {
            "rows": [
                {"code": "1r2", "size": 2},
                {"code": "2r2", "size": 2},
            ],
        },
        "photos": {
            "before": [{"path": image_path}],
            "after": [{"path": "C:/missing/after.jpg"}],
        },
    }


def _template():
    return {
        "fields": [
            {"type": "text", "source": "report.report_id", "cell": "A1"},
            {"type": "image", "source": "photos.before[0].path", "anchor": "B2"},
            {"type": "image", "source": "photos.after[0].path", "anchor": "C2"},
            {"type": "table", "source": "welds.rows", "max_rows": 1, "columns": ["code", "size"]},
        ]
    }


def test_dry_run_reports_image_existence_and_table_overflow(tmp_path):
    before = tmp_path / "before.jpg"
    before.write_bytes(b"fake")

    result = dry_run_template_for_report(_report(str(before)), _template())

    assert result["ok"] is False
    assert result["summary"]["field_count"] == 4
    assert result["placements"][1]["exists"] is True
    assert result["placements"][2]["exists"] is False
    assert result["placements"][3]["row_count"] == 2
    assert result["placements"][3]["overflow_count"] == 1
    assert any(issue["code"] == "missing_image_file" for issue in result["issues"])
    overflow = next(issue for issue in result["issues"] if issue["code"] == "table_overflow")
    assert overflow["severity"] == "error"


def test_dry_run_pdf_overlay_new_page_predicts_render_pages(tmp_path):
    before = tmp_path / "before.jpg"
    before.write_bytes(b"fake")
    template = {
        "kind": "pdf_overlay",
        "base_pdf": "vendor.pdf",
        "fields": [
            {
                "type": "table",
                "source": "welds.rows",
                "page": 1,
                "rect_norm": [0.1, 0.1, 0.8, 0.3],
                "rows_per_page": 1,
                "overflow": "new_page",
                "columns": ["code", "size"],
            }
        ],
    }

    result = dry_run_template_for_report(_report(str(before)), template)

    assert result["ok"] is True
    assert result["placements"][0]["overflow_count"] == 1
    assert result["placements"][0]["render_pages"] == 2
    assert not any(issue["code"] == "overflow_mode_unsupported" for issue in result["issues"])


def test_dry_run_table_image_cells_check_paths(tmp_path):
    before = tmp_path / "before.jpg"
    before.write_bytes(b"fake")
    report = _report(str(before))
    report["photos"]["before"].append({"path": str(tmp_path / "missing.jpg"), "name": "missing.jpg"})
    template = {
        "kind": "pdf_overlay",
        "base_pdf": "vendor.pdf",
        "fields": [
            {
                "type": "table",
                "source": "photos.before[*]",
                "page": 1,
                "rect_norm": [0.1, 0.1, 0.8, 0.3],
                "rows_per_page": 5,
                "overflow": "new_page",
                "columns": [
                    {"source": "path", "cell_type": "image"},
                    {"source": "name"},
                ],
            }
        ],
    }

    result = dry_run_template_for_report(report, template)

    assert result["ok"] is True
    assert result["placements"][0]["image_cell_count"] == 2
    assert any(issue["code"] == "missing_image_file" and issue["source"] == "photos.before[*].path" for issue in result["issues"])


def test_dry_run_pdf_overlay_truncate_is_explicitly_unsupported(tmp_path):
    before = tmp_path / "before.jpg"
    before.write_bytes(b"fake")
    template = {
        "kind": "pdf_overlay",
        "base_pdf": "vendor.pdf",
        "fields": [
            {
                "type": "table",
                "source": "welds.rows",
                "page": 1,
                "rect_norm": [0.1, 0.1, 0.8, 0.3],
                "rows_per_page": 1,
                "overflow": "truncate",
                "columns": ["code", "size"],
            }
        ],
    }

    result = dry_run_template_for_report(_report(str(before)), template)

    assert result["ok"] is False
    assert any(issue["code"] == "overflow_mode_unsupported" for issue in result["issues"])


def test_dry_run_report_set_adds_report_label_to_issues(tmp_path):
    before = tmp_path / "before.jpg"
    before.write_bytes(b"fake")
    report_set = {"reports": [_report(str(before))]}

    result = dry_run_template_for_report_set(report_set, _template())

    assert result["ok"] is False
    assert result["report_count"] == 1
    assert result["issues"][0]["report"] == "R-1"


def test_dry_run_stops_on_invalid_template():
    result = dry_run_template_for_report(
        _report(),
        {"fields": [{"type": "text", "source": "report.bad_field"}]},
    )

    assert result["ok"] is False
    assert result["issues"][0]["code"] == "template_invalid"


def test_dry_run_reports_unmapped_data_fields():
    template = {
        "fields": [
            {"type": "text", "source": "report.report_id", "cell": "A1"},
            {"type": "table", "source": "welds.rows", "max_rows": 5, "columns": ["code"]},
        ]
    }

    result = dry_run_template_for_report(_report(), template)

    paths = {item["path"] for item in result["coverage"]["unmapped_data"]}
    assert result["ok"] is True
    assert "report.folder" in paths
    assert "report.description" in paths
    assert "welds.rows[*].size" in paths
    assert "welds.rows[*].code" not in paths
    assert any(issue["code"] == "unmapped_data" for issue in result["issues"])


def test_dry_run_coverage_ignore_suppresses_expected_unmapped_fields():
    template = {
        "coverage_ignore": ["report.description", "welds.rows[*].size"],
        "fields": [
            {"type": "text", "source": "report.report_id", "cell": "A1"},
            {"type": "table", "source": "welds.rows", "max_rows": 5, "columns": ["code"]},
        ],
    }

    result = dry_run_template_for_report(_report(), template)

    paths = {item["path"] for item in result["coverage"]["unmapped_data"]}
    assert "report.description" not in paths
    assert "welds.rows[*].size" not in paths


def test_dry_run_does_not_report_photo_wildcard_root_as_unmapped_data():
    result = dry_run_template_for_report(
        _report("C:/missing/before.jpg"),
        {
            "fields": [
                {"type": "text", "source": "report.report_id", "cell": "A1"},
            ],
        },
    )

    paths = {item["path"] for item in result["coverage"]["unmapped_data"]}
    assert "photos.before[*]" not in paths
    assert "photos.after[*]" not in paths
