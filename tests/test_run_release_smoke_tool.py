# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


def _make_attachment_project(root: Path) -> None:
    folder = root / "attachments" / "20260112" / "0547_AG"
    folder.mkdir(parents=True)
    (folder / "GroupWeld.txt").write_text("1r2\n2r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("現場 release smoke", encoding="utf-8")
    Image.new("RGB", (120, 80), (220, 80, 60)).save(folder / "before_1.jpg")
    Image.new("RGB", (120, 80), (80, 160, 90)).save(folder / "after_1.jpg")


def run_tool(repo: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(repo / "tools" / "run_release_smoke.py"), *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_release_smoke_repairs_and_runs_output_center(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    init = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "check_startup_guard.py"),
            "--project-root",
            str(tmp_path),
            "--repair",
            "--json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    _make_attachment_project(tmp_path)
    output_dir = tmp_path / "staging" / "release_smoke"

    result = run_tool(
        repo,
        "--project-root",
        str(tmp_path),
        "--output",
        str(output_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["startup"]["decision"]["action"] == "healthy"
    assert data["output_center"]["report_count"] == 1
    assert Path(data["output_center"]["files"]["statistics_xlsx"]).exists()


def test_release_smoke_blocks_wrong_folder(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    (tmp_path / "random.txt").write_text("not a project", encoding="utf-8")

    result = run_tool(repo, "--project-root", str(tmp_path), "--json")

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["reason"] == "startup_blocked"
    assert data["startup"]["decision"]["action"] == "blocked_wrong_folder"
