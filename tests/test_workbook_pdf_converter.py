# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import workbook_pdf_converter
from capabilities import CapabilityResult
from workbook_pdf_converter import convert_workbook_to_pdf


def _write_valid_pdf(path: Path) -> None:
    pypdf = __import__("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)


def test_convert_workbook_to_pdf_uses_libreoffice_and_validates_output(monkeypatch, tmp_path):
    workbook = tmp_path / "source.xlsx"
    workbook.write_bytes(b"fake workbook")
    output = tmp_path / "out.pdf"

    monkeypatch.setattr(
        workbook_pdf_converter,
        "detect_libreoffice",
        lambda executable=None: CapabilityResult(
            name="libreoffice",
            available=True,
            reason="LibreOffice headless 可用",
            detail="fake",
            executable="fake-soffice",
        ),
    )

    def fake_run(command, *, timeout_seconds):
        outdir = Path(command[command.index("--outdir") + 1])
        input_path = Path(command[-1])
        _write_valid_pdf(outdir / f"{input_path.stem}.pdf")
        return subprocess.CompletedProcess(command, 0, stdout="converted", stderr="")

    monkeypatch.setattr(workbook_pdf_converter, "_run_libreoffice_command", fake_run)

    result = convert_workbook_to_pdf(workbook, output)

    assert result["ok"] is True
    assert result["path"] == str(output.resolve())
    assert result["result_schema_version"] == "output_result.v1"
    assert result["outputs"][0]["kind"] == "pdf"
    assert result["pdf_validation"]["pages"] == 1
    assert output.exists()


def test_convert_workbook_to_pdf_reports_unavailable_libreoffice(monkeypatch, tmp_path):
    workbook = tmp_path / "source.xlsx"
    workbook.write_bytes(b"fake workbook")

    monkeypatch.setattr(
        workbook_pdf_converter,
        "detect_libreoffice",
        lambda executable=None: CapabilityResult(
            name="libreoffice",
            available=False,
            reason="找不到 LibreOffice/soffice 執行檔",
            detail="missing",
        ),
    )

    result = convert_workbook_to_pdf(workbook, tmp_path / "out.pdf")

    assert result["ok"] is False
    assert result["result_schema_version"] == "output_result.v1"
    assert result["outputs"] == []
    assert result["issues"][0]["code"] == "libreoffice_unavailable"


def test_convert_workbook_to_pdf_reports_timeout_as_failure(monkeypatch, tmp_path):
    workbook = tmp_path / "source.xlsx"
    workbook.write_bytes(b"fake workbook")

    monkeypatch.setattr(
        workbook_pdf_converter,
        "detect_libreoffice",
        lambda executable=None: CapabilityResult(
            name="libreoffice",
            available=True,
            reason="LibreOffice headless 可用",
            executable="fake-soffice",
        ),
    )

    def fake_run(command, *, timeout_seconds):
        raise workbook_pdf_converter.LibreOfficeCommandTimeout(
            command,
            timeout_seconds,
            stdout="partial out",
            stderr="partial err",
        )

    monkeypatch.setattr(workbook_pdf_converter, "_run_libreoffice_command", fake_run)

    result = convert_workbook_to_pdf(workbook, tmp_path / "out.pdf", timeout_seconds=1)

    assert result["ok"] is False
    assert result["issues"][0]["code"] == "libreoffice_timeout"
    assert "1 秒" in result["issues"][0]["message"]
    assert result["stdout"] == "partial out"
    assert result["stderr"] == "partial err"


def test_convert_workbook_to_pdf_reports_spawn_failure(monkeypatch, tmp_path):
    workbook = tmp_path / "source.xlsx"
    workbook.write_bytes(b"fake workbook")

    monkeypatch.setattr(
        workbook_pdf_converter,
        "detect_libreoffice",
        lambda executable=None: CapabilityResult(
            name="libreoffice",
            available=True,
            reason="LibreOffice headless 可用",
            executable="fake-soffice",
        ),
    )

    def fake_run(command, *, timeout_seconds):
        raise PermissionError("denied")

    monkeypatch.setattr(workbook_pdf_converter, "_run_libreoffice_command", fake_run)

    result = convert_workbook_to_pdf(workbook, tmp_path / "out.pdf")

    assert result["ok"] is False
    assert result["issues"][0]["code"] == "libreoffice_spawn_failed"
    assert "denied" in result["issues"][0]["message"]


def test_convert_workbook_to_pdf_uses_configured_soffice_path(monkeypatch, tmp_path):
    workbook = tmp_path / "source.xlsx"
    workbook.write_bytes(b"fake workbook")
    captured = {}

    monkeypatch.setattr(workbook_pdf_converter, "get_soffice_path", lambda: "C:/configured/soffice.exe")

    def fake_detect(executable=None):
        captured["executable"] = executable
        return CapabilityResult(
            name="libreoffice",
            available=False,
            reason="找不到 LibreOffice/soffice 執行檔",
            detail="missing",
        )

    monkeypatch.setattr(workbook_pdf_converter, "detect_libreoffice", fake_detect)

    result = convert_workbook_to_pdf(workbook, tmp_path / "out.pdf")

    assert result["ok"] is False
    assert captured["executable"] == "C:/configured/soffice.exe"


def test_convert_workbook_pdf_cli_json_reports_missing_soffice(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    workbook = tmp_path / "source.xlsx"
    workbook.write_bytes(b"fake workbook")
    output = tmp_path / "out.pdf"

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "convert_workbook_pdf.py"),
            str(workbook),
            str(output),
            "--soffice",
            str(tmp_path / "missing-soffice.exe"),
            "--json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["issues"][0]["code"] == "libreoffice_unavailable"
    assert not output.exists()
