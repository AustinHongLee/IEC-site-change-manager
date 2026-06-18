# -*- coding: utf-8 -*-

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_cli_export_template_outputs_unpriced_rows_only(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    source_path = tmp_path / "material_pricebook.json"
    output_path = tmp_path / "template.csv"
    source_path.write_text(
        json.dumps({
            "items": [
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
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "export_pricebook_template.py"),
            str(output_path),
            "--source",
            str(source_path),
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "已匯出 未定價 價目 1 筆" in result.stdout
    with open(output_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["id"] == "pipe-empty"
