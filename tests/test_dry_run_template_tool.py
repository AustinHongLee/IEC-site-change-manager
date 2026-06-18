# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


def test_dry_run_template_cli_uses_report_set_json_without_output_files(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    before = tmp_path / "before.jpg"
    before.write_bytes(b"fake")
    template_path = tmp_path / "template.json"
    report_set_path = tmp_path / "report_set.json"
    template_path.write_text(
        json.dumps({
            "fields": [
                {"type": "text", "source": "report.report_id", "cell": "A1"},
                {"type": "image", "source": "photos.before[0].path", "anchor": "B2"},
                {"type": "table", "source": "welds.rows", "max_rows": 1, "columns": ["code"]},
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    report_set_path.write_text(
        json.dumps({
            "reports": [{
                "report": {"report_id": "R-1", "folder": "001_1r2"},
                "photos": {"before": [{"path": str(before)}]},
                "welds": {"rows": [{"code": "1r2"}, {"code": "2r2"}]},
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "dry_run_template.py"),
            str(template_path),
            "--report-set",
            str(report_set_path),
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    assert "日誌啟動" not in result.stdout
    assert "DRY-RUN template" in result.stdout
    assert "R-1" in result.stdout
    assert "table_overflow" in result.stdout


def test_dry_run_template_cli_json_output(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    template_path = tmp_path / "template.json"
    report_set_path = tmp_path / "report_set.json"
    template_path.write_text(
        json.dumps({"fields": [{"type": "text", "source": "report.report_id"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    report_set_path.write_text(
        json.dumps({"reports": [{"report": {"report_id": "R-1"}}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "dry_run_template.py"),
            str(template_path),
            "--report-set",
            str(report_set_path),
            "--json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["report_count"] == 1
    assert data["reports"][0]["report"] == "R-1"


def test_dry_run_template_cli_json_includes_unmapped_data(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    template_path = tmp_path / "template.json"
    report_set_path = tmp_path / "report_set.json"
    template_path.write_text(
        json.dumps({"fields": [{"type": "text", "source": "report.report_id"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    report_set_path.write_text(
        json.dumps({
            "reports": [{
                "report": {"report_id": "R-1", "folder": "001_1r2", "description": "現場修改"},
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "dry_run_template.py"),
            str(template_path),
            "--report-set",
            str(report_set_path),
            "--json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    paths = {item["path"] for item in data["reports"][0]["coverage"]["unmapped_data"]}
    assert "report.folder" in paths
    assert "report.description" in paths


def test_dry_run_template_cli_json_stdout_stays_parseable_when_collecting_project(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    template_path = tmp_path / "template.json"
    template_path.write_text(
        json.dumps({"fields": [{"type": "text", "source": "report.folder"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "dry_run_template.py"),
            str(template_path),
            "--json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "reports" in data
