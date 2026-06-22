# -*- coding: utf-8 -*-
"""Run a real CLI output smoke against a copied PyInstaller onedir package."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


_THIS = Path(__file__).resolve().parent
_ROOT = _THIS.parent
_CONTROL_DIR = _ROOT / "control"
if str(_CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTROL_DIR))

from console_io import configure_utf8_stdio


DEFAULT_PACKAGE_DIR = _ROOT / "dist" / "IEC-site-change-manager"
DEFAULT_EXE_NAME = "IEC-site-change-manager.exe"
DEFAULT_SOURCE_PROJECT = _ROOT
DEFAULT_CASE_DATE = "20260112"
DEFAULT_CASE_FOLDER = "0547_AG"


def _tail(text: str, *, limit: int = 80) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-limit:])


def _issue(code: str, message: str, path: Path | str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": str(path)}


def _run_command(command: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout_tail": _tail(exc.stdout or ""),
            "stderr_tail": _tail(exc.stderr or ""),
            "error": "timeout",
            "command": command,
        }
    except OSError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "error": "os_error",
            "command": command,
        }

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "error": "",
        "command": command,
    }


@contextmanager
def _workspace(work_dir: str | Path | None, *, keep: bool) -> Iterator[Path]:
    if work_dir:
        root = Path(work_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        yield root
        return

    if keep:
        root = Path(tempfile.mkdtemp(prefix="iec_pkg_cli_smoke_")).resolve()
        yield root
        return

    with tempfile.TemporaryDirectory(prefix="iec_pkg_cli_smoke_") as temp:
        yield Path(temp).resolve()


def copy_package_for_smoke(package_dir: str | Path, work_root: str | Path) -> Path:
    package = Path(package_dir).resolve()
    target = Path(work_root).resolve() / package.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(package, target)
    return target


def copy_attachment_case(
    source_project: str | Path,
    target_project: str | Path,
    *,
    case_date: str,
    case_folder: str,
) -> Path:
    source = Path(source_project).resolve() / "attachments" / case_date / case_folder
    target = Path(target_project).resolve() / "attachments" / case_date / case_folder
    if not source.is_dir():
        raise FileNotFoundError(source)
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target


def find_cli_smoke_outputs(project_root: str | Path, *, case_date: str, min_kb: float = 0.3) -> list[dict[str, Any]]:
    output_dir = Path(project_root).resolve() / "output" / case_date
    outputs: list[dict[str, Any]] = []
    for path in sorted(output_dir.glob("*.xlsm"), key=lambda item: item.name.lower()):
        size = path.stat().st_size if path.is_file() else 0
        outputs.append({
            "path": str(path),
            "name": path.name,
            "bytes": size,
            "ok": size >= min_kb * 1024,
        })
    return outputs


def _load_records_summary(project_root: Path) -> dict[str, Any]:
    records_path = project_root / "records" / "records.json"
    if not records_path.is_file():
        return {"path": str(records_path), "exists": False}
    try:
        data = json.loads(records_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"path": str(records_path), "exists": True, "error": str(exc)}
    return {
        "path": str(records_path),
        "exists": True,
        "records": len(data.get("records") or []),
        "details": len(data.get("details") or []),
        "materials": len(data.get("materials") or []),
    }


def _classify_cli_failure(cli: dict[str, Any]) -> str:
    text = "\n".join([str(cli.get("stdout_tail") or ""), str(cli.get("stderr_tail") or "")])
    if cli.get("returncode") == 4 or "Excel COM" in text or "Microsoft Excel" in text:
        return "excel_com_unavailable"
    if cli.get("error") == "timeout":
        return "cli_timeout"
    if cli.get("error"):
        return str(cli.get("error"))
    return "cli_failed"


def run_packaged_cli_smoke(
    package_dir: str | Path = DEFAULT_PACKAGE_DIR,
    *,
    exe_name: str = DEFAULT_EXE_NAME,
    source_project: str | Path = DEFAULT_SOURCE_PROJECT,
    case_date: str = DEFAULT_CASE_DATE,
    case_folder: str = DEFAULT_CASE_FOLDER,
    timeout: int = 180,
    no_pdf: bool = True,
    work_dir: str | Path | None = None,
    keep_work_dir: bool = False,
) -> dict[str, Any]:
    package = Path(package_dir).resolve()
    source = Path(source_project).resolve()
    issues: list[dict[str, str]] = []

    result: dict[str, Any] = {
        "ran": True,
        "ok": False,
        "package_dir": str(package),
        "source_project": str(source),
        "case": {"date": case_date, "folder": case_folder},
        "work_dir": "",
        "smoke_project": "",
        "initialize": None,
        "cli": None,
        "outputs": [],
        "records": None,
        "issues": issues,
    }

    if not package.is_dir():
        issues.append(_issue("missing_package_dir", "找不到 package 資料夾。", package))
        result["reason"] = "missing_package_dir"
        return result
    if not (package / exe_name).is_file():
        issues.append(_issue("missing_exe", "找不到 package 入口 exe。", package / exe_name))
        result["reason"] = "missing_exe"
        return result
    source_case = source / "attachments" / case_date / case_folder
    if not source_case.is_dir():
        issues.append(_issue("missing_attachment_case", "找不到 CLI smoke 測試附件資料夾。", source_case))
        result["reason"] = "missing_attachment_case"
        return result

    with _workspace(work_dir, keep=keep_work_dir) as work_root:
        result["work_dir"] = str(work_root)
        smoke_project = copy_package_for_smoke(package, work_root)
        result["smoke_project"] = str(smoke_project)
        exe_path = smoke_project / exe_name

        initialize = _run_command(
            [str(exe_path), "--repair-project", "--health-check"],
            cwd=smoke_project,
            timeout=timeout,
        )
        result["initialize"] = initialize
        if not initialize.get("ok"):
            issues.append(_issue("initialize_failed", "package copy 無法完成第一次開啟初始化。", exe_path))
            result["reason"] = "initialize_failed"
            return result

        try:
            copied_case = copy_attachment_case(
                source,
                smoke_project,
                case_date=case_date,
                case_folder=case_folder,
            )
        except OSError as exc:
            issues.append(_issue("copy_attachment_failed", str(exc), source_case))
            result["reason"] = "copy_attachment_failed"
            return result
        result["copied_case"] = str(copied_case)

        command = [str(exe_path), "--cli", "--date", case_date, "--force"]
        if no_pdf:
            command.append("--no-pdf")
        cli = _run_command(command, cwd=smoke_project, timeout=timeout)
        result["cli"] = cli
        result["outputs"] = find_cli_smoke_outputs(smoke_project, case_date=case_date)
        result["records"] = _load_records_summary(smoke_project)

        valid_outputs = [item for item in result["outputs"] if item.get("ok")]
        records = result["records"] or {}
        records_ok = bool(records.get("exists")) and records.get("records", 0) >= 1 and records.get("details", 0) >= 1
        result["ok"] = bool(cli.get("ok") and valid_outputs and records_ok)
        if not result["ok"]:
            if not cli.get("ok"):
                result["reason"] = _classify_cli_failure(cli)
                issues.append(_issue("cli_failed", "package exe CLI 真輸出執行失敗。", exe_path))
            elif not valid_outputs:
                result["reason"] = "missing_xlsm_output"
                issues.append(_issue("missing_xlsm_output", "CLI 執行後找不到有效 XLSM 修改單。", smoke_project / "output"))
            elif not records_ok:
                result["reason"] = "records_not_updated"
                issues.append(_issue("records_not_updated", "CLI 執行後 records.json 沒有寫入主表與明細。", smoke_project / "records"))
        return result


def _print_text(result: dict[str, Any]) -> None:
    print(f"Packaged CLI smoke：{'成功' if result.get('ok') else '失敗'}")
    print(f"package_dir：{result.get('package_dir')}")
    print(f"case：{(result.get('case') or {}).get('date')}/{(result.get('case') or {}).get('folder')}")
    if result.get("work_dir"):
        print(f"work_dir：{result.get('work_dir')}")
    init = result.get("initialize") or {}
    if init:
        print(f"initialize：{'OK' if init.get('ok') else 'NG'} returncode={init.get('returncode')}")
    cli = result.get("cli") or {}
    if cli:
        print(f"cli：{'OK' if cli.get('ok') else 'NG'} returncode={cli.get('returncode')}")
    records = result.get("records") or {}
    if records:
        print(
            "records："
            f"exists={records.get('exists')} "
            f"records={records.get('records', 0)} "
            f"details={records.get('details', 0)} "
            f"materials={records.get('materials', 0)}"
        )
    for output in result.get("outputs") or []:
        print(f"- output：{'OK' if output.get('ok') else 'NG'} {output.get('name')} ({output.get('bytes')} bytes)")
    for issue in result.get("issues") or []:
        print(f"- [error] {issue.get('code')}: {issue.get('message')}")
        if issue.get("path"):
            print(f"  {issue.get('path')}")
    if result.get("reason"):
        print(f"reason：{result.get('reason')}")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="執行打包後 exe CLI 真輸出冒煙")
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR), help="要測試的 onedir package")
    parser.add_argument("--exe-name", default=DEFAULT_EXE_NAME, help="入口 exe 檔名")
    parser.add_argument("--source-project", default=str(DEFAULT_SOURCE_PROJECT), help="測試附件來源專案")
    parser.add_argument("--date", default=DEFAULT_CASE_DATE, help="測試日期資料夾")
    parser.add_argument("--folder", default=DEFAULT_CASE_FOLDER, help="測試附件資料夾")
    parser.add_argument("--timeout", type=int, default=180, help="單一 exe 呼叫 timeout 秒數")
    parser.add_argument("--with-pdf", action="store_true", help="同時要求 CLI 匯出 PDF")
    parser.add_argument("--work-dir", default="", help="指定暫存工作資料夾")
    parser.add_argument("--keep-work-dir", action="store_true", help="保留自動建立的暫存工作資料夾")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args()

    result = run_packaged_cli_smoke(
        args.package_dir,
        exe_name=args.exe_name,
        source_project=args.source_project,
        case_date=args.date,
        case_folder=args.folder,
        timeout=args.timeout,
        no_pdf=not args.with_pdf,
        work_dir=args.work_dir or None,
        keep_work_dir=args.keep_work_dir,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
