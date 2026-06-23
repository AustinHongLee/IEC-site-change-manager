# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))

from app_info import APP_VERSION


def current_git_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def write_build_info(package: Path, repo: Path, *, git_commit: str | None = None, app_version: str = APP_VERSION):
    info = {
        "schema_version": "build_info.v1",
        "app_version": app_version,
        "git_commit": git_commit or current_git_commit(repo),
        "built_at": "2026-06-22T00:00:00Z",
        "source_dirty": False,
    }
    (package / "_internal" / "build_info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")


def make_package(root: Path):
    repo = Path(__file__).resolve().parents[1]
    package = root / "IEC-site-change-manager"
    (package / "_internal" / "template").mkdir(parents=True)
    (package / "_internal" / "control" / "image").mkdir(parents=True)
    (package / "_internal" / "control" / "wizard_data.json").write_text("{}", encoding="utf-8")
    (package / "_internal" / "material_pricebook_seed.json").write_text("[]", encoding="utf-8")
    write_build_info(package, repo)
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
    assert data["build_info"]["ok"] is True
    assert data["build_info"]["data"]["git_commit"] == current_git_commit(repo)
    assert data["health_check"]["ran"] is False


def test_check_release_package_rejects_missing_build_info(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    package = make_package(tmp_path)
    (package / "_internal" / "build_info.json").unlink()

    result = run_tool(repo, "--package-dir", str(package), "--json")

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert any(issue["code"] == "build_info_missing" for issue in data["issues"])


def test_check_release_package_rejects_stale_build_commit(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    package = make_package(tmp_path)
    write_build_info(package, repo, git_commit="deadbeef")

    result = run_tool(repo, "--package-dir", str(package), "--json")

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["build_info"]["expected_git_commit"] == current_git_commit(repo)
    assert any(issue["code"] == "build_info_git_commit_mismatch" for issue in data["issues"])


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
