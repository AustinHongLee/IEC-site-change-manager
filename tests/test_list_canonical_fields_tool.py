# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path


def test_list_canonical_fields_cli_outputs_catalog_paths():
    repo = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, str(repo / "tools" / "list_canonical_fields.py")],
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
    assert "photos.before[*]" in result.stdout
    assert "photos.before[*].path" in result.stdout
    assert "photos.before[0..n]" not in result.stdout
