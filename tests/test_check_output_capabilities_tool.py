# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


def test_check_output_capabilities_cli_outputs_json():
    repo = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "check_output_capabilities.py"),
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
    keys = {item["key"] for item in data["capabilities"]}
    assert "site_statistics_xlsx" in keys
    assert "xlsx_template" in keys
    assert "pdf_overlay" in keys
    assert "workbook_pdf_libreoffice" in keys
    assert "legacy_xlsx_com" in keys
