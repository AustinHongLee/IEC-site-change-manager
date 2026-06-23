# -*- coding: utf-8 -*-
"""Build and verify the PyInstaller onedir release package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_THIS = Path(__file__).resolve().parent
_ROOT = _THIS.parent
_CONTROL_DIR = _ROOT / "control"
if str(_CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(_CONTROL_DIR))
if str(_THIS) not in sys.path:
    sys.path.insert(0, str(_THIS))

from app_info import APP_VERSION
from check_release_package import (
    DEFAULT_CLI_SMOKE_DATE,
    DEFAULT_CLI_SMOKE_FOLDER,
    DEFAULT_CLI_SMOKE_SOURCE_PROJECT,
    DEFAULT_PACKAGE_DIR,
    check_release_package,
)
from console_io import configure_utf8_stdio


DEFAULT_SPEC = _ROOT / "packaging" / "IEC-site-change-manager.spec"
DEFAULT_ARCHIVE_DIR = _ROOT / "dist" / "releases"
GENERATED_BUILD_INFO = _ROOT / "packaging" / "generated" / "build_info.json"
BUILD_INFO_SCHEMA = "build_info.v1"


def _git_stdout(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(message or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _current_git_commit() -> str:
    return _git_stdout("rev-parse", "HEAD")


def _source_dirty() -> bool:
    completed = subprocess.run(
        ["git", "diff-index", "--quiet", "HEAD", "--"],
        cwd=_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode == 0:
        return False
    if completed.returncode == 1:
        return True
    message = (completed.stderr or completed.stdout or "").strip()
    raise RuntimeError(message or "git diff-index --quiet HEAD -- failed")


def _write_build_info(path: Path = GENERATED_BUILD_INFO) -> dict[str, Any]:
    info: dict[str, Any] = {
        "schema_version": BUILD_INFO_SCHEMA,
        "app_version": APP_VERSION,
        "git_commit": _current_git_commit(),
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_dirty": _source_dirty(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(path), **info}


def _run_pyinstaller(spec_path: Path, *, clean: bool = True) -> dict[str, Any]:
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    if clean:
        command.append("--clean")
    command.append(str(spec_path))
    completed = subprocess.run(
        command,
        cwd=_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": _tail_lines(completed.stdout),
        "stderr_tail": _tail_lines(completed.stderr),
    }


def _tail_lines(text: str, *, limit: int = 40) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-limit:])


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_name() -> str:
    return f"IEC-site-change-manager_{APP_VERSION}_win64_onedir.zip"


def create_release_archive(
    package_dir: str | Path,
    *,
    archive_dir: str | Path = DEFAULT_ARCHIVE_DIR,
) -> dict[str, Any]:
    package = Path(package_dir).resolve()
    output = Path(archive_dir).resolve()
    if output == package or output.is_relative_to(package):
        raise ValueError("archive_dir must not be inside package_dir")

    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / _archive_name()
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if archive_path.exists():
        archive_path.unlink()
    if checksum_path.exists():
        checksum_path.unlink()

    file_count = 0
    dir_count = 0
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(package.rglob("*"), key=lambda path: str(path).lower()):
            arcname = (Path(package.name) / item.relative_to(package)).as_posix()
            if item.is_dir():
                archive.writestr(arcname + "/", "")
                dir_count += 1
                continue
            if not item.is_file():
                continue
            archive.write(item, arcname)
            file_count += 1

    checksum = _sha256_file(archive_path)
    checksum_path.write_text(f"{checksum}  {archive_path.name}\n", encoding="utf-8")
    return {
        "path": str(archive_path),
        "checksum_path": str(checksum_path),
        "sha256": checksum,
        "bytes": archive_path.stat().st_size,
        "file_count": file_count,
        "dir_count": dir_count,
    }


def build_release(
    *,
    spec_path: str | Path = DEFAULT_SPEC,
    package_dir: str | Path = DEFAULT_PACKAGE_DIR,
    skip_build: bool = False,
    run_health_check: bool = True,
    run_cli_smoke: bool = True,
    cli_smoke_source_project: str | Path = DEFAULT_CLI_SMOKE_SOURCE_PROJECT,
    cli_smoke_date: str = DEFAULT_CLI_SMOKE_DATE,
    cli_smoke_folder: str = DEFAULT_CLI_SMOKE_FOLDER,
    cli_smoke_timeout: int = 180,
    cli_smoke_with_pdf: bool = False,
    create_archive: bool = False,
    archive_dir: str | Path = DEFAULT_ARCHIVE_DIR,
) -> dict[str, Any]:
    spec = Path(spec_path).resolve()
    package = Path(package_dir).resolve()
    result: dict[str, Any] = {
        "ok": False,
        "app_version": APP_VERSION,
        "spec_path": str(spec),
        "package_dir": str(package),
        "build_info": {"generated": False},
        "build": {"skipped": skip_build},
        "package_check": None,
        "archive": None,
    }

    if not skip_build:
        try:
            result["build_info"] = {"generated": True, **_write_build_info()}
        except Exception as exc:
            result["reason"] = "build_info_failed"
            result["build_info"] = {"generated": False, "error": str(exc)}
            return result
        build = _run_pyinstaller(spec)
        build["skipped"] = False
        result["build"] = build
        if build["returncode"] != 0:
            result["reason"] = "pyinstaller_failed"
            return result

    package_check = check_release_package(
        package,
        run_health_check=run_health_check,
        run_cli_smoke=run_cli_smoke,
        cli_smoke_source_project=cli_smoke_source_project,
        cli_smoke_date=cli_smoke_date,
        cli_smoke_folder=cli_smoke_folder,
        cli_smoke_timeout=cli_smoke_timeout,
        cli_smoke_with_pdf=cli_smoke_with_pdf,
    )
    result["package_check"] = package_check
    result["ok"] = bool(package_check.get("ok"))
    if not result["ok"]:
        result["reason"] = "package_check_failed"
        return result

    if create_archive:
        try:
            result["archive"] = create_release_archive(package, archive_dir=archive_dir)
        except Exception as exc:
            result["ok"] = False
            result["reason"] = "archive_failed"
            result["archive"] = {"error": str(exc)}
    return result


def _print_text(result: dict[str, Any]) -> None:
    print(f"Release build：{'成功' if result.get('ok') else '失敗'}")
    print(f"app_version：{result.get('app_version')}")
    print(f"spec_path：{result.get('spec_path')}")
    print(f"package_dir：{result.get('package_dir')}")
    build = result.get("build") or {}
    if build.get("skipped"):
        print("build：skipped")
    else:
        print(f"build：returncode={build.get('returncode')}")
    package = result.get("package_check") or {}
    if package:
        print(f"package_check：{'OK' if package.get('ok') else 'NG'}")
        for issue in package.get("issues") or []:
            print(f"- [{issue.get('severity')}] {issue.get('code')}: {issue.get('message')}")
        cli_smoke = package.get("cli_smoke") or {}
        if cli_smoke.get("ran"):
            print(f"cli_smoke：{'OK' if cli_smoke.get('ok') else 'NG'} reason={cli_smoke.get('reason', '')}")
    archive = result.get("archive") or {}
    if archive:
        if archive.get("path"):
            print(f"archive：{archive.get('path')}")
            print(f"sha256：{archive.get('sha256')}")
        else:
            print(f"archive：NG {archive.get('error')}")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="建置並驗證 release package")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC), help="PyInstaller spec 路徑")
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR), help="release package 資料夾")
    parser.add_argument("--skip-build", action="store_true", help="略過 PyInstaller，只跑 package gate")
    parser.add_argument("--no-health-check", action="store_true", help="package gate 不執行 exe --health-check")
    cli_smoke_group = parser.add_mutually_exclusive_group()
    cli_smoke_group.add_argument(
        "--cli-smoke",
        dest="cli_smoke",
        action="store_true",
        default=True,
        help="package gate 執行打包後 exe CLI 真輸出冒煙（預設）",
    )
    cli_smoke_group.add_argument(
        "--no-cli-smoke",
        dest="cli_smoke",
        action="store_false",
        help="略過打包後 exe CLI 真輸出冒煙；只適合快速結構檢查",
    )
    parser.add_argument("--cli-smoke-source-project", default=str(DEFAULT_CLI_SMOKE_SOURCE_PROJECT), help="CLI smoke 測試附件來源專案")
    parser.add_argument("--cli-smoke-date", default=DEFAULT_CLI_SMOKE_DATE, help="CLI smoke 測試日期")
    parser.add_argument("--cli-smoke-folder", default=DEFAULT_CLI_SMOKE_FOLDER, help="CLI smoke 測試附件資料夾")
    parser.add_argument("--cli-smoke-timeout", type=int, default=180, help="CLI smoke 單一 exe 呼叫 timeout 秒數")
    parser.add_argument("--cli-smoke-with-pdf", action="store_true", help="CLI smoke 同時要求匯出 PDF")
    parser.add_argument("--archive", action="store_true", help="package gate 通過後產生 zip 與 sha256")
    parser.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR), help="release archive 輸出資料夾")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args()

    result = build_release(
        spec_path=args.spec,
        package_dir=args.package_dir,
        skip_build=args.skip_build,
        run_health_check=not args.no_health_check,
        run_cli_smoke=args.cli_smoke,
        cli_smoke_source_project=args.cli_smoke_source_project,
        cli_smoke_date=args.cli_smoke_date,
        cli_smoke_folder=args.cli_smoke_folder,
        cli_smoke_timeout=args.cli_smoke_timeout,
        cli_smoke_with_pdf=args.cli_smoke_with_pdf,
        create_archive=args.archive,
        archive_dir=args.archive_dir,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
