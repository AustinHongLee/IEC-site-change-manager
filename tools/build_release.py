# -*- coding: utf-8 -*-
"""Build and verify the PyInstaller onedir release package."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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
from check_release_package import DEFAULT_PACKAGE_DIR, check_release_package
from console_io import configure_utf8_stdio


DEFAULT_SPEC = _ROOT / "packaging" / "IEC-site-change-manager.spec"


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


def build_release(
    *,
    spec_path: str | Path = DEFAULT_SPEC,
    package_dir: str | Path = DEFAULT_PACKAGE_DIR,
    skip_build: bool = False,
    run_health_check: bool = True,
) -> dict[str, Any]:
    spec = Path(spec_path).resolve()
    package = Path(package_dir).resolve()
    result: dict[str, Any] = {
        "ok": False,
        "app_version": APP_VERSION,
        "spec_path": str(spec),
        "package_dir": str(package),
        "build": {"skipped": skip_build},
        "package_check": None,
    }

    if not skip_build:
        build = _run_pyinstaller(spec)
        build["skipped"] = False
        result["build"] = build
        if build["returncode"] != 0:
            result["reason"] = "pyinstaller_failed"
            return result

    package_check = check_release_package(
        package,
        run_health_check=run_health_check,
    )
    result["package_check"] = package_check
    result["ok"] = bool(package_check.get("ok"))
    if not result["ok"]:
        result["reason"] = "package_check_failed"
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


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="建置並驗證 release package")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC), help="PyInstaller spec 路徑")
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR), help="release package 資料夾")
    parser.add_argument("--skip-build", action="store_true", help="略過 PyInstaller，只跑 package gate")
    parser.add_argument("--no-health-check", action="store_true", help="package gate 不執行 exe --health-check")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args()

    result = build_release(
        spec_path=args.spec,
        package_dir=args.package_dir,
        skip_build=args.skip_build,
        run_health_check=not args.no_health_check,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
