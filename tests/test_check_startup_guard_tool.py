# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


def run_tool(repo: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(repo / "tools" / "check_startup_guard.py"), *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_check_startup_guard_json_reports_first_open(tmp_path):
    repo = Path(__file__).resolve().parents[1]

    result = run_tool(repo, "--project-root", str(tmp_path), "--json")

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["decision"]["action"] == "initialize"
    assert data["decision"]["can_auto_repair"] is True


def test_check_startup_guard_blocks_wrong_folder(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    (tmp_path / "random.txt").write_text("not a project", encoding="utf-8")

    result = run_tool(repo, "--project-root", str(tmp_path), "--json")

    assert result.returncode == 2
    data = json.loads(result.stdout)
    assert data["decision"]["action"] == "blocked_wrong_folder"
    assert data["decision"]["can_continue"] is False


def test_check_startup_guard_repair_initializes_empty_project(tmp_path):
    repo = Path(__file__).resolve().parents[1]

    result = run_tool(repo, "--project-root", str(tmp_path), "--repair", "--json")

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["decision"]["action"] == "healthy"
    assert "建立 settings.json" in data["repaired"]
    assert (tmp_path / "settings.json").exists()
    assert (tmp_path / "records" / "records.json").exists()
