# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


def test_run_demo_output_smoke_cli_outputs_json(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "demo"

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "run_demo_output_smoke.py"),
            "--output",
            str(output_dir),
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
    assert data["ok"] is True
    assert Path(data["files"]["rendered_xlsx"]).exists()
    assert Path(data["files"]["site_statistics_xlsx"]).exists()


def test_run_demo_output_smoke_cli_outputs_edge_matrix_json(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "edge"

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "run_demo_output_smoke.py"),
            "--output",
            str(output_dir),
            "--edge-matrix",
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
    assert data["ok"] is True
    assert data["report_count"] == 5
    assert any(case["folder"] == "0603_MANY_PHOTOS" for case in data["cases"])
