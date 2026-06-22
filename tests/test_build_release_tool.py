# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


def make_package(root: Path):
    package = root / "IEC-site-change-manager"
    (package / "_internal" / "template").mkdir(parents=True)
    (package / "_internal" / "control" / "image").mkdir(parents=True)
    (package / "_internal" / "control" / "wizard_data.json").write_text("{}", encoding="utf-8")
    (package / "_internal" / "material_pricebook_seed.json").write_text("[]", encoding="utf-8")
    (package / "IEC-site-change-manager.exe").write_text("fake exe", encoding="utf-8")
    return package


def run_tool(repo: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(repo / "tools" / "build_release.py"), *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_build_release_skip_build_runs_package_gate(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    package = make_package(tmp_path)

    result = run_tool(
        repo,
        "--skip-build",
        "--no-health-check",
        "--package-dir",
        str(package),
        "--json",
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["build"]["skipped"] is True
    assert data["package_check"]["startup"]["decision"]["action"] == "initialize"


def test_build_release_skip_build_reports_package_failure(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    package = make_package(tmp_path)
    (package / "extra.txt").write_text("not part of package", encoding="utf-8")

    result = run_tool(
        repo,
        "--skip-build",
        "--no-health-check",
        "--package-dir",
        str(package),
        "--json",
    )

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["reason"] == "package_check_failed"
