# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from diagnostics import collect_support_bundle


def test_collect_support_bundle_writes_zip_with_json_and_health_text(tmp_path):
    output = tmp_path / "out"

    result = collect_support_bundle(
        tmp_path,
        output_dir=output,
        timestamp=datetime(2026, 6, 22, 12, 0, 0),
    )

    assert result["ok"] is True
    assert result["startup_action"] == "initialize"
    bundle_path = result["bundle_path"]
    assert bundle_path.endswith("support_bundle_20260622_120000.zip")
    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        assert names == {"diagnostics.json", "health_check.txt"}
        diagnostics = json.loads(bundle.read("diagnostics.json").decode("utf-8"))
        health = bundle.read("health_check.txt").decode("utf-8")

    assert diagnostics["schema_version"] == "support_bundle.v1"
    assert diagnostics["app"]["version"]
    assert diagnostics["app"]["paths"]["template_6_exists"] is True
    assert diagnostics["app"]["paths"]["wizard_data_exists"] is True
    assert diagnostics["project"]["startup"]["decision"]["action"] == "initialize"
    assert "IEC Site Change Manager" in health


def test_main_diagnostics_cli_creates_bundle(tmp_path):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    output = tmp_path / "diag"

    result = subprocess.run(
        [
            sys.executable,
            os.path.join(repo, "control", "main.py"),
            "--diagnostics",
            "--diagnostics-output",
            str(output),
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "支援診斷包:" in result.stdout
    assert list(output.glob("support_bundle_*.zip"))
