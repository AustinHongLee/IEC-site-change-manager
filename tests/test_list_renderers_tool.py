# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


def test_list_renderers_cli_outputs_json_registry():
    repo = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "list_renderers.py"),
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
    kinds = {renderer["kind"] for renderer in data["renderers"]}
    assert "xlsx_template" in kinds
    assert "pdf_overlay" in kinds
    assert "xlsx_com" in kinds
