# -*- coding: utf-8 -*-
"""Convert workbook files to PDF without Excel COM using LibreOffice."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from capabilities import detect_libreoffice, format_libreoffice_unavailable
from output_result import attach_output_envelope, output_item, step_item
from settings_manager import get_soffice_path


WORKBOOK_EXTENSIONS = {".xlsx", ".xlsm", ".ods"}


class LibreOfficeCommandTimeout(Exception):
    def __init__(self, command: list[str], timeout_seconds: int, stdout: str = "", stderr: str = ""):
        super().__init__(f"LibreOffice command timed out after {timeout_seconds} seconds")
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.stdout = stdout
        self.stderr = stderr


def convert_workbook_to_pdf(
    workbook_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str] | None = None,
    *,
    soffice_path: str | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    workbook = Path(workbook_path).resolve()
    output = Path(output_path).resolve() if output_path else workbook.with_suffix(".pdf")

    if not workbook.exists():
        return _failure("input_missing", f"找不到 workbook：{workbook}", output)
    if workbook.suffix.lower() not in WORKBOOK_EXTENSIONS:
        return _failure("unsupported_workbook_type", f"不支援的 workbook 格式：{workbook.suffix}", output)

    capability = detect_libreoffice(executable=_resolve_soffice_path(soffice_path))
    if not capability.available:
        return _failure(
            "libreoffice_unavailable",
            format_libreoffice_unavailable(capability),
            output,
            capability=asdict(capability),
        )

    with tempfile.TemporaryDirectory(prefix="iec_lo_pdf_") as tmp:
        tmp_path = Path(tmp)
        profile_path = tmp_path / "profile"
        out_dir = tmp_path / "out"
        profile_path.mkdir()
        out_dir.mkdir()
        command = [
            capability.executable,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--norestore",
            f"-env:UserInstallation={profile_path.resolve().as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(workbook),
        ]
        try:
            completed = _run_libreoffice_command(command, timeout_seconds=timeout_seconds)
        except LibreOfficeCommandTimeout as exc:
            return _failure(
                "libreoffice_timeout",
                f"LibreOffice PDF 轉檔逾時（{timeout_seconds} 秒），已嘗試停止轉檔程序",
                output,
                stdout=exc.stdout,
                stderr=exc.stderr,
                command=command,
                capability=asdict(capability),
            )
        except OSError as exc:
            return _failure(
                "libreoffice_spawn_failed",
                f"無法啟動 LibreOffice/soffice：{exc}",
                output,
                command=command,
                capability=asdict(capability),
            )
        generated = out_dir / f"{workbook.stem}.pdf"
        if completed.returncode != 0:
            return _failure(
                "libreoffice_convert_failed",
                "LibreOffice PDF 轉檔失敗",
                output,
                stdout=completed.stdout,
                stderr=completed.stderr,
                command=command,
                capability=asdict(capability),
            )
        if not generated.exists():
            return _failure(
                "pdf_output_missing",
                "LibreOffice 回報成功，但找不到轉出的 PDF",
                output,
                stdout=completed.stdout,
                stderr=completed.stderr,
                command=command,
                capability=asdict(capability),
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output.with_suffix(output.suffix + ".tmp")
        shutil.copyfile(generated, temp_output)
        os.replace(temp_output, output)

    validation = _validate_pdf(output)
    result = {
        "ok": validation["ok"],
        "path": str(output) if validation["ok"] else "",
        "input": str(workbook),
        "converter": "libreoffice",
        "capability": asdict(capability),
        "pdf_validation": validation,
        "issues": [] if validation["ok"] else [validation["issue"]],
    }
    return attach_output_envelope(
        result,
        outputs=[output_item(kind="pdf", path=result["path"], role="primary", label="PDF")],
        capabilities={"libreoffice": asdict(capability)},
        steps=[
            step_item(key="libreoffice_convert", ok=True, label="LibreOffice workbook to PDF"),
            step_item(key="pdf_validation", ok=validation["ok"], label="PDF readable validation"),
        ],
    )


def _validate_pdf(path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = len(reader.pages)
    except Exception as exc:
        return {
            "ok": False,
            "pages": 0,
            "issue": {
                "severity": "error",
                "code": "pdf_validation_failed",
                "message": f"PDF 轉出後無法讀取：{exc}",
            },
        }
    if pages <= 0:
        return {
            "ok": False,
            "pages": 0,
            "issue": {
                "severity": "error",
                "code": "pdf_has_no_pages",
                "message": "PDF 轉出後沒有頁面",
            },
        }
    return {"ok": True, "pages": pages}


def _run_libreoffice_command(command: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess:
    popen_kwargs: dict[str, Any] = {
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(command, **popen_kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        stdout = _text_from_timeout_output(exc.stdout)
        stderr = _text_from_timeout_output(exc.stderr)
        _terminate_process_tree(process)
        try:
            tail_stdout, tail_stderr = process.communicate(timeout=5)
            stdout += _text_from_timeout_output(tail_stdout)
            stderr += _text_from_timeout_output(tail_stderr)
        except Exception:
            pass
        raise LibreOfficeCommandTimeout(command, timeout_seconds, stdout, stderr) from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout=stdout, stderr=stderr)


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
            return
        except Exception:
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except Exception:
            pass
    try:
        process.kill()
    except Exception:
        pass


def _text_from_timeout_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _resolve_soffice_path(soffice_path: str | None) -> str | None:
    if soffice_path is not None:
        return soffice_path
    return get_soffice_path() or None


def _failure(
    code: str,
    message: str,
    output: Path,
    *,
    stdout: str = "",
    stderr: str = "",
    command: list[str] | None = None,
    capability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issue = {
        "severity": "error",
        "code": code,
        "message": message,
    }
    return attach_output_envelope({
        "ok": False,
        "path": "",
        "input": "",
        "output": str(output),
        "converter": "libreoffice",
        "capability": capability or {},
        "stdout": stdout,
        "stderr": stderr,
        "command": command or [],
        "issues": [issue],
    }, capabilities={"libreoffice": capability or {}})
