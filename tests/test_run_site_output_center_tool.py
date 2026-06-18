# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


def test_run_site_output_center_cli_outputs_formal_names(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    attachments = tmp_path / "attachments"
    folder = attachments / "20260112" / "0547_AG"
    folder.mkdir(parents=True)
    (folder / "GroupWeld.txt").write_text("1r2\n2r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("現場展示測試", encoding="utf-8")
    Image.new("RGB", (120, 80), (220, 80, 60)).save(folder / "before_1.jpg")
    Image.new("RGB", (120, 80), (80, 160, 90)).save(folder / "after_1.jpg")
    output_dir = tmp_path / "site_output"

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "run_site_output_center.py"),
            "--project-root",
            str(tmp_path),
            "--attachments-root",
            str(attachments),
            "--output",
            str(output_dir),
            "--json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["output_center"] == str(output_dir.resolve())
    assert "showcase" not in data
    assert Path(data["files"]["report_set"]).name == "canonical_report_set.json"
    assert Path(data["files"]["statistics_xlsx"]).name == "site_statistics.xlsx"
    assert Path(data["files"]["summary"]).name == "output_center_summary.json"
    assert (output_dir / ".iec_site_output_center").exists()
    render_names = {Path(item["path"]).name for item in data["renders"]}
    assert "site_summary_0547_AG.pdf" in render_names
    assert "site_photo_grid_0547_AG.pdf" in render_names


def test_run_site_output_center_refuses_to_overwrite_unmarked_folder(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    output_dir = tmp_path / "not_output_center"
    output_dir.mkdir()
    (output_dir / "important.txt").write_text("keep", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "run_site_output_center.py"),
            "--project-root",
            str(tmp_path),
            "--attachments-root",
            str(attachments),
            "--output",
            str(output_dir),
            "--overwrite",
            "--json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode != 0
    assert "拒絕覆寫非輸出中心資料夾" in result.stderr
