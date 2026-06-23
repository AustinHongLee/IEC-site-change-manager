# -*- coding: utf-8 -*-
"""
Validate a PyInstaller onedir release package before handing it to users.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from app_info import APP_VERSION
from console_io import configure_utf8_stdio
from project_guard import build_startup_decision, inspect_project
from run_packaged_cli_smoke import (
    DEFAULT_CASE_DATE as DEFAULT_CLI_SMOKE_DATE,
    DEFAULT_CASE_FOLDER as DEFAULT_CLI_SMOKE_FOLDER,
    DEFAULT_SOURCE_PROJECT as DEFAULT_CLI_SMOKE_SOURCE_PROJECT,
    run_packaged_cli_smoke,
)


DEFAULT_PACKAGE_DIR = Path(_ROOT) / "dist" / "IEC-site-change-manager"
DEFAULT_EXE_NAME = "IEC-site-change-manager.exe"
ALLOWED_TOP_LEVEL = {DEFAULT_EXE_NAME, "_internal"}
BUILD_INFO_SCHEMA = "build_info.v1"
REQUIRED_INTERNAL_ASSETS = (
    ("template", "dir"),
    ("control/image", "dir"),
    ("control/wizard_data.json", "file"),
    ("material_pricebook_seed.json", "file"),
)


def _issue(severity: str, code: str, message: str, path: Path | str = "") -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "path": str(path),
    }


def _guard_issue_to_dict(issue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "title": issue.title,
        "message": issue.message,
        "path": issue.path,
        "auto_fixable": issue.auto_fixable,
    }


def _check_asset(path: Path, kind: str) -> bool:
    if kind == "dir":
        return path.is_dir()
    if kind == "file":
        return path.is_file()
    raise ValueError(f"unknown asset kind: {kind}")


def _current_git_commit() -> tuple[str, str]:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        return "", message or "git rev-parse HEAD failed"
    return completed.stdout.strip(), ""


def _validate_build_info(internal: Path) -> dict[str, Any]:
    path = internal / "build_info.json"
    result: dict[str, Any] = {
        "ok": False,
        "path": str(path),
        "data": None,
        "expected_app_version": APP_VERSION,
        "expected_git_commit": "",
        "errors": [],
        "warnings": [],
    }
    if not path.is_file():
        result["errors"].append({"code": "missing", "message": "缺少 _internal/build_info.json。"})
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["errors"].append({"code": "invalid_json", "message": f"build_info.json 不是有效 JSON：{exc}"})
        return result

    if not isinstance(data, dict):
        result["errors"].append({"code": "invalid_shape", "message": "build_info.json 必須是 JSON object。"})
        return result

    result["data"] = data
    expected_commit, git_error = _current_git_commit()
    result["expected_git_commit"] = expected_commit
    if git_error:
        result["errors"].append({"code": "git_unavailable", "message": f"無法取得目前 git HEAD：{git_error}"})
    if data.get("schema_version") != BUILD_INFO_SCHEMA:
        result["errors"].append({"code": "schema_mismatch", "message": "build_info schema_version 不正確。"})
    if data.get("app_version") != APP_VERSION:
        result["errors"].append({"code": "app_version_mismatch", "message": "build_info app_version 與 app_info.APP_VERSION 不一致。"})
    if expected_commit and data.get("git_commit") != expected_commit:
        result["errors"].append({"code": "git_commit_mismatch", "message": "build_info git_commit 不是目前 HEAD。"})
    if data.get("source_dirty") is True:
        result["warnings"].append({"code": "source_dirty", "message": "此 package 建置時工作樹不是完全乾淨。"})

    result["ok"] = not result["errors"]
    return result


def _run_health_check(exe_path: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(exe_path), "--health-check"],
            cwd=exe_path.parent,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ran": True,
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "error": "timeout",
        }
    except OSError as exc:
        return {
            "ran": True,
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "error": "os_error",
        }

    return {
        "ran": True,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "error": "",
    }


def _run_version_check(exe_path: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(exe_path), "--version"],
            cwd=exe_path.parent,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ran": True,
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "error": "timeout",
            "expected_version": APP_VERSION,
        }
    except OSError as exc:
        return {
            "ran": True,
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "error": "os_error",
            "expected_version": APP_VERSION,
        }

    stdout = completed.stdout or ""
    return {
        "ran": True,
        "ok": completed.returncode == 0 and APP_VERSION in stdout,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": completed.stderr,
        "error": "" if APP_VERSION in stdout else "version_mismatch",
        "expected_version": APP_VERSION,
    }


def _run_diagnostics_probe(exe_path: Path, expected_internal: Path, timeout: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="iec_diag_probe_") as temp:
        output = Path(temp)
        try:
            completed = subprocess.run(
                [str(exe_path), "--diagnostics", "--diagnostics-output", str(output)],
                cwd=exe_path.parent,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "ran": True,
                "ok": False,
                "returncode": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "error": "timeout",
            }
        except OSError as exc:
            return {
                "ran": True,
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
                "error": "os_error",
            }

        result: dict[str, Any] = {
            "ran": True,
            "ok": False,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "error": "",
            "paths": {},
        }
        if completed.returncode != 0:
            result["error"] = "diagnostics_failed"
            return result

        bundles = sorted(output.glob("support_bundle_*.zip"))
        if not bundles:
            result["error"] = "missing_bundle"
            return result

        try:
            with zipfile.ZipFile(bundles[-1]) as bundle:
                diagnostics = json.loads(bundle.read("diagnostics.json").decode("utf-8"))
        except Exception as exc:
            result["error"] = f"invalid_bundle: {exc}"
            return result

        paths = ((diagnostics.get("app") or {}).get("paths") or {})
        result["paths"] = paths
        resource_dir = Path(str(paths.get("resource_dir") or "")).resolve()
        expected = expected_internal.resolve()
        required_exists = (
            bool(paths.get("template_6_exists"))
            and bool(paths.get("template_27_exists"))
            and bool(paths.get("wizard_data_exists"))
            and bool(paths.get("material_pricebook_seed_exists"))
        )
        result["ok"] = resource_dir == expected and required_exists
        if resource_dir != expected:
            result["error"] = "resource_dir_mismatch"
        elif not required_exists:
            result["error"] = "missing_runtime_resource"
        return result


def check_release_package(
    package_dir: str | Path = DEFAULT_PACKAGE_DIR,
    *,
    exe_name: str = DEFAULT_EXE_NAME,
    run_health_check: bool = False,
    health_timeout: int = 60,
    run_cli_smoke: bool = False,
    cli_smoke_source_project: str | Path = DEFAULT_CLI_SMOKE_SOURCE_PROJECT,
    cli_smoke_date: str = DEFAULT_CLI_SMOKE_DATE,
    cli_smoke_folder: str = DEFAULT_CLI_SMOKE_FOLDER,
    cli_smoke_timeout: int = 180,
    cli_smoke_with_pdf: bool = False,
) -> dict[str, Any]:
    package = Path(package_dir).resolve()
    exe_path = package / exe_name
    internal = package / "_internal"
    issues: list[dict[str, str]] = []

    if not package.is_dir():
        issues.append(_issue("error", "missing_package_dir", "找不到 release package 資料夾。", package))
        return {
            "ok": False,
            "package_dir": str(package),
            "exe_path": str(exe_path),
            "startup": None,
            "build_info": {"ok": False, "path": "", "errors": [{"code": "missing_package_dir"}], "warnings": []},
            "version_check": {"ran": False},
            "health_check": {"ran": False},
            "diagnostics_probe": {"ran": False},
            "cli_smoke": {"ran": False},
            "issues": issues,
        }

    if not exe_path.is_file():
        issues.append(_issue("error", "missing_exe", "找不到 release package 入口 exe。", exe_path))
    if not internal.is_dir():
        issues.append(_issue("error", "missing_internal_dir", "找不到 PyInstaller _internal 資料夾。", internal))

    allowed = set(ALLOWED_TOP_LEVEL)
    allowed.add(exe_name)
    for child in sorted(package.iterdir(), key=lambda item: item.name.lower()):
        if child.name not in allowed:
            issues.append(_issue("error", "top_level_extra", "release package 頂層不應夾帶專案資料或雜檔。", child))

    for relative, kind in REQUIRED_INTERNAL_ASSETS:
        asset_path = internal / relative
        if not _check_asset(asset_path, kind):
            issues.append(_issue("error", "missing_internal_asset", f"缺少打包內嵌資產：{relative}", asset_path))

    build_info = _validate_build_info(internal)
    for problem in build_info.get("errors") or []:
        issues.append(_issue("error", f"build_info_{problem.get('code')}", problem.get("message", "build_info 驗證失敗。"), build_info.get("path", "")))
    for problem in build_info.get("warnings") or []:
        issues.append(_issue("warning", f"build_info_{problem.get('code')}", problem.get("message", "build_info 有警告。"), build_info.get("path", "")))

    guard = inspect_project(package)
    decision = build_startup_decision(guard)
    startup = {
        "state": guard.state,
        "decision": {
            "action": decision.action,
            "title": decision.title,
            "can_continue": decision.can_continue,
            "can_auto_repair": decision.can_auto_repair,
        },
        "issues": [_guard_issue_to_dict(issue) for issue in guard.issues],
    }
    if decision.action != "initialize":
        issues.append(
            _issue(
                "error",
                "unexpected_startup_action",
                "乾淨 release package 應被啟動守門判定為第一次開啟。",
                package,
            )
        )

    version_check = {"ran": False}
    health = {"ran": False}
    diagnostics_probe = {"ran": False}
    cli_smoke = {"ran": False}
    if run_health_check:
        if exe_path.is_file():
            version_check = _run_version_check(exe_path, health_timeout)
            if not version_check.get("ok"):
                issues.append(_issue("error", "exe_version_check_failed", "exe --version 與 app_info.APP_VERSION 不一致。", exe_path))
            health = _run_health_check(exe_path, health_timeout)
            if not health.get("ok"):
                issues.append(_issue("error", "exe_health_check_failed", "exe --health-check 執行失敗。", exe_path))
            diagnostics_probe = _run_diagnostics_probe(exe_path, internal, health_timeout)
            if not diagnostics_probe.get("ok"):
                issues.append(
                    _issue(
                        "error",
                        "exe_diagnostics_probe_failed",
                        "exe 診斷包無法確認打包資源路徑與必要資產。",
                        exe_path,
                    )
                )
        else:
            version_check = {"ran": False, "ok": False, "error": "missing_exe"}
            health = {"ran": False, "ok": False, "error": "missing_exe"}
            diagnostics_probe = {"ran": False, "ok": False, "error": "missing_exe"}

    if run_cli_smoke:
        if exe_path.is_file():
            cli_smoke = run_packaged_cli_smoke(
                package,
                exe_name=exe_name,
                source_project=cli_smoke_source_project,
                case_date=cli_smoke_date,
                case_folder=cli_smoke_folder,
                timeout=cli_smoke_timeout,
                no_pdf=not cli_smoke_with_pdf,
            )
            if not cli_smoke.get("ok"):
                reason = cli_smoke.get("reason") or "unknown"
                issues.append(
                    _issue(
                        "error",
                        "exe_cli_smoke_failed",
                        f"exe CLI 真輸出冒煙失敗：{reason}",
                        exe_path,
                    )
                )
        else:
            cli_smoke = {"ran": False, "ok": False, "error": "missing_exe"}

    has_errors = any(issue["severity"] == "error" for issue in issues)
    return {
        "ok": not has_errors,
        "package_dir": str(package),
        "exe_path": str(exe_path),
        "startup": startup,
        "build_info": build_info,
        "version_check": version_check,
        "health_check": health,
        "diagnostics_probe": diagnostics_probe,
        "cli_smoke": cli_smoke,
        "issues": issues,
    }


def _print_text(result: dict[str, Any]) -> None:
    print(f"Release package：{'合格' if result.get('ok') else '不合格'}")
    print(f"package_dir：{result.get('package_dir')}")
    print(f"exe_path：{result.get('exe_path')}")
    startup = result.get("startup") or {}
    decision = startup.get("decision") or {}
    if decision:
        print(f"startup：{startup.get('state')} / {decision.get('action')} - {decision.get('title')}")
    build_info = result.get("build_info") or {}
    if build_info.get("path"):
        data = build_info.get("data") or {}
        commit = str(data.get("git_commit") or "")
        print(
            "build_info："
            f"{'OK' if build_info.get('ok') else 'NG'} "
            f"version={data.get('app_version', '')} "
            f"commit={commit[:12]}"
        )
    version = result.get("version_check") or {}
    if version.get("ran"):
        print(f"exe version：{'OK' if version.get('ok') else 'NG'} expected={version.get('expected_version')}")
    health = result.get("health_check") or {}
    if health.get("ran"):
        print(f"exe health-check：{'OK' if health.get('ok') else 'NG'} returncode={health.get('returncode')}")
    probe = result.get("diagnostics_probe") or {}
    if probe.get("ran"):
        print(f"exe diagnostics probe：{'OK' if probe.get('ok') else 'NG'}")
    cli_smoke = result.get("cli_smoke") or {}
    if cli_smoke.get("ran"):
        case = cli_smoke.get("case") or {}
        print(
            "exe CLI smoke："
            f"{'OK' if cli_smoke.get('ok') else 'NG'} "
            f"case={case.get('date')}/{case.get('folder')} "
            f"reason={cli_smoke.get('reason', '')}"
        )
    for issue in result.get("issues") or []:
        print(f"- [{issue.get('severity')}] {issue.get('code')}: {issue.get('message')}")
        if issue.get("path"):
            print(f"  {issue.get('path')}")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="檢查 PyInstaller release package")
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR), help="要檢查的 onedir package")
    parser.add_argument("--exe-name", default=DEFAULT_EXE_NAME, help="入口 exe 檔名")
    parser.add_argument("--run-health-check", action="store_true", help="執行 exe --health-check")
    parser.add_argument("--health-timeout", type=int, default=60, help="exe health-check timeout 秒數")
    parser.add_argument("--run-cli-smoke", action="store_true", help="執行打包後 exe CLI 真輸出冒煙")
    parser.add_argument("--cli-smoke-source-project", default=str(DEFAULT_CLI_SMOKE_SOURCE_PROJECT), help="CLI smoke 測試附件來源專案")
    parser.add_argument("--cli-smoke-date", default=DEFAULT_CLI_SMOKE_DATE, help="CLI smoke 測試日期")
    parser.add_argument("--cli-smoke-folder", default=DEFAULT_CLI_SMOKE_FOLDER, help="CLI smoke 測試附件資料夾")
    parser.add_argument("--cli-smoke-timeout", type=int, default=180, help="CLI smoke 單一 exe 呼叫 timeout 秒數")
    parser.add_argument("--cli-smoke-with-pdf", action="store_true", help="CLI smoke 同時要求匯出 PDF")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args()

    result = check_release_package(
        args.package_dir,
        exe_name=args.exe_name,
        run_health_check=args.run_health_check,
        health_timeout=args.health_timeout,
        run_cli_smoke=args.run_cli_smoke,
        cli_smoke_source_project=args.cli_smoke_source_project,
        cli_smoke_date=args.cli_smoke_date,
        cli_smoke_folder=args.cli_smoke_folder,
        cli_smoke_timeout=args.cli_smoke_timeout,
        cli_smoke_with_pdf=args.cli_smoke_with_pdf,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
