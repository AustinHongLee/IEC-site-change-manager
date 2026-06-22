# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "tools"))

from run_packaged_cli_smoke import (
    copy_attachment_case,
    find_cli_smoke_outputs,
    run_packaged_cli_smoke,
)


def _make_package(root: Path) -> Path:
    package = root / "IEC-site-change-manager"
    package.mkdir()
    (package / "_internal").mkdir()
    (package / "IEC-site-change-manager.exe").write_text("fake exe", encoding="utf-8")
    return package


def test_packaged_cli_smoke_reports_missing_attachment_case(tmp_path):
    package = _make_package(tmp_path)
    source_project = tmp_path / "source"
    source_project.mkdir()

    result = run_packaged_cli_smoke(
        package,
        source_project=source_project,
        case_date="20260112",
        case_folder="0547_AG",
    )

    assert result["ok"] is False
    assert result["reason"] == "missing_attachment_case"
    assert any(issue["code"] == "missing_attachment_case" for issue in result["issues"])


def test_copy_attachment_case_copies_source_folder(tmp_path):
    source_project = tmp_path / "source"
    source_case = source_project / "attachments" / "20260112" / "0547_AG"
    source_case.mkdir(parents=True)
    (source_case / "note.txt").write_text("smoke", encoding="utf-8")
    target_project = tmp_path / "target"

    copied = copy_attachment_case(
        source_project,
        target_project,
        case_date="20260112",
        case_folder="0547_AG",
    )

    assert copied == target_project / "attachments" / "20260112" / "0547_AG"
    assert (copied / "note.txt").read_text(encoding="utf-8") == "smoke"


def test_find_cli_smoke_outputs_marks_small_files_invalid(tmp_path):
    output_dir = tmp_path / "output" / "20260112"
    output_dir.mkdir(parents=True)
    (output_dir / "small.xlsm").write_bytes(b"x")
    (output_dir / "large.xlsm").write_bytes(b"x" * 1024)

    outputs = find_cli_smoke_outputs(tmp_path, case_date="20260112", min_kb=0.3)

    by_name = {item["name"]: item for item in outputs}
    assert by_name["small.xlsm"]["ok"] is False
    assert by_name["large.xlsm"]["ok"] is True
