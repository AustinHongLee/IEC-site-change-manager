# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


def test_run_real_attachments_showcase_cli_outputs_json(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    attachments = tmp_path / "attachments"
    folder = attachments / "20260112" / "0547_AG"
    folder.mkdir(parents=True)
    (folder / "GroupWeld.txt").write_text("1r2\n2r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("現場展示測試", encoding="utf-8")
    (folder / "materials.txt").write_text(
        "Elbow (彎頭), 2\", , 白鐵, 1 個,\n"
        "Tee (三通), 2\", , 白鐵, 1 個,\n"
        "Flange (法蘭), 2\", , 白鐵, 1 個,\n",
        encoding="utf-8",
    )
    Image.new("RGB", (120, 80), (220, 80, 60)).save(folder / "before_1.jpg")
    Image.new("RGB", (120, 80), (80, 160, 90)).save(folder / "after_1.jpg")
    output_dir = tmp_path / "showcase"

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "run_real_attachments_showcase.py"),
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
    assert data["report_count"] == 1
    assert Path(data["files"]["report_set"]).exists()
    assert Path(data["files"]["statistics_xlsx"]).exists()
    assert data["renders"][0]["ok"] is True
    assert data["renders"][0]["pages"] == 2
    assert Path(data["renders"][0]["path"]).exists()


def test_run_real_attachments_showcase_cli_can_filter_include_keys(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    attachments = tmp_path / "attachments"
    first = attachments / "20260112" / "0547_AG"
    second = attachments / "20250820" / "55_2a2"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "GroupWeld.txt").write_text("1r2\n2r2\n", encoding="utf-8")
    (first / "note.txt").write_text("現場展示測試", encoding="utf-8")
    (second / "GroupWeld.txt").write_text("1r1\n", encoding="utf-8")
    (second / "note.txt").write_text("另一筆資料", encoding="utf-8")
    Image.new("RGB", (120, 80), (220, 80, 60)).save(first / "before_1.jpg")
    Image.new("RGB", (120, 80), (80, 160, 90)).save(first / "after_1.jpg")
    Image.new("RGB", (120, 80), (120, 120, 120)).save(second / "before.jpg")
    Image.new("RGB", (120, 80), (40, 120, 120)).save(second / "after.jpg")
    output_dir = tmp_path / "showcase"

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "run_real_attachments_showcase.py"),
            "--project-root",
            str(tmp_path),
            "--attachments-root",
            str(attachments),
            "--output",
            str(output_dir),
            "--include",
            "20260112/0547_AG",
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
    assert data["scope"]["mode"] == "filtered"
    assert data["report_count"] == 1
    assert {item["folder"] for item in data["renders"]} == {"0547_AG"}
    assert len(data["renders"]) == 2


def test_run_real_attachments_showcase_cli_can_choose_output_content(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    attachments = tmp_path / "attachments"
    folder = attachments / "20260112" / "0547_AG"
    folder.mkdir(parents=True)
    (folder / "GroupWeld.txt").write_text("1r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("現場展示測試", encoding="utf-8")
    Image.new("RGB", (120, 80), (220, 80, 60)).save(folder / "before_1.jpg")
    Image.new("RGB", (120, 80), (80, 160, 90)).save(folder / "after_1.jpg")
    output_dir = tmp_path / "showcase"

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "run_real_attachments_showcase.py"),
            "--project-root",
            str(tmp_path),
            "--attachments-root",
            str(attachments),
            "--output",
            str(output_dir),
            "--no-statistics",
            "--no-summary-pdf",
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
    assert data["content"]["statistics_xlsx"] is False
    assert data["content"]["summary_pdf"] is False
    assert data["content"]["photo_grid_pdf"] is True
    assert data["files"]["statistics_xlsx"] == ""
    assert [item["template"] for item in data["renders"]] == ["photo_grid"]
    assert Path(data["renders"][0]["path"]).exists()


def test_run_real_attachments_showcase_refuses_to_overwrite_unmarked_folder(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    output_dir = tmp_path / "not_showcase"
    output_dir.mkdir()
    (output_dir / "important.txt").write_text("keep", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "run_real_attachments_showcase.py"),
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
    assert "拒絕覆寫非 showcase 資料夾" in result.stderr
