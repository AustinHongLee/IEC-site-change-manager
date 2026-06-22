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
        [sys.executable, str(repo / "tools" / "check_release_package.py"), *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_check_release_package_accepts_fresh_onedir(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    package = make_package(tmp_path)

    result = run_tool(repo, "--package-dir", str(package), "--json")

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["startup"]["decision"]["action"] == "initialize"
    assert data["health_check"]["ran"] is False


def test_check_release_package_rejects_missing_asset(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    package = make_package(tmp_path)
    (package / "_internal" / "material_pricebook_seed.json").unlink()

    result = run_tool(repo, "--package-dir", str(package), "--json")

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert any(issue["code"] == "missing_internal_asset" for issue in data["issues"])


def test_check_release_package_rejects_top_level_project_data(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    package = make_package(tmp_path)
    (package / "records").mkdir()

    result = run_tool(repo, "--package-dir", str(package), "--json")

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert any(issue["code"] == "top_level_extra" for issue in data["issues"])
