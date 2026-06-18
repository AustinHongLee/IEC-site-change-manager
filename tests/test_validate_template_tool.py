# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


def test_validate_template_cli_accepts_valid_template(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    template_path = tmp_path / "template.json"
    template_path.write_text(
        json.dumps({
            "template_id": "sample",
            "schema_version": "template_mapping.v1",
            "kind": "xlsx_template",
            "fields": [
                {"type": "text", "source": "report.report_id", "cell": "A1"},
                {"type": "image", "source": "photos.before[0].path", "anchor": "B2"},
                {"type": "table", "source": "materials.rows", "max_rows": 10, "columns": ["component", "qty", "unit"]},
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(repo / "tools" / "validate_template.py"), str(template_path)],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "通過模板驗證" in result.stdout


def test_validate_template_cli_rejects_unknown_field(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    template_path = tmp_path / "bad_template.json"
    template_path.write_text(
        json.dumps({
            "fields": [{"type": "text", "source": "report.bad_field", "cell": "A1"}],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(repo / "tools" / "validate_template.py"), str(template_path)],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    assert "report.bad_field" in result.stdout


def test_validate_template_cli_lists_canonical_fields(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    dummy_path = tmp_path / "unused.json"

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "validate_template.py"),
            str(dummy_path),
            "--list-fields",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "日誌啟動" not in result.stdout
    assert "report.report_id" in result.stdout
    assert "materials.rows" in result.stdout


def test_validate_template_cli_accepts_pdf_overlay_template(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    template_path = tmp_path / "pdf_overlay.json"
    template_path.write_text(
        json.dumps({
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
                    "columns": ["component", "qty", "unit"],
                },
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(repo / "tools" / "validate_template.py"), str(template_path)],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "通過模板驗證" in result.stdout
