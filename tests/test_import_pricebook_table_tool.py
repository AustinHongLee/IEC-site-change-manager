# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path


def test_cli_price_table_dry_run_does_not_create_target_file(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    csv_path = tmp_path / "price_table.csv"
    target_path = tmp_path / "material_pricebook.json"
    csv_path.write_text(
        "\n".join([
            "零件類型,材質,單位,單價,來源",
            "Valve (閥),CS,個,300,合約",
        ]),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "import_pricebook_table.py"),
            str(csv_path),
            "--target",
            str(target_path),
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "DRY-RUN" in result.stdout
    assert "將新增: 1" in result.stdout
    assert not target_path.exists()
