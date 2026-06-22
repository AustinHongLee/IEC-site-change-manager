# -*- coding: utf-8 -*-
"""CLI wrapper for creating a read-only support bundle."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from console_io import configure_utf8_stdio
from diagnostics import collect_support_bundle


def _print_text(result: dict) -> None:
    print("Support bundle：完成")
    print(f"bundle_path：{result.get('bundle_path')}")
    print(f"project_root：{result.get('project_root')}")
    print(f"startup_action：{result.get('startup_action')}")
    severity = result.get("integrity_severity") or {}
    print(
        "integrity："
        f"error={severity.get('error', 0)}, "
        f"warning={severity.get('warning', 0)}, "
        f"info={severity.get('info', 0)}"
    )


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="產生支援診斷包")
    parser.add_argument("--project-root", default=_ROOT, help="要診斷的專案資料夾")
    parser.add_argument("--output", default="", help="診斷包輸出資料夾")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args()

    result = collect_support_bundle(
        Path(args.project_root),
        output_dir=Path(args.output) if args.output else None,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
