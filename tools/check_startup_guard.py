# -*- coding: utf-8 -*-
"""
Check project startup guard decisions for a target project folder.
"""

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
from project_guard import build_startup_decision, format_guard_report, inspect_project, repair_project


def _issue_to_dict(issue) -> dict:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "title": issue.title,
        "message": issue.message,
        "path": issue.path,
        "auto_fixable": issue.auto_fixable,
    }


def _result_to_jsonable(result) -> dict:
    decision = build_startup_decision(result)
    return {
        "root": result.root,
        "state": result.state,
        "decision": {
            "action": decision.action,
            "title": decision.title,
            "message": decision.message,
            "can_continue": decision.can_continue,
            "can_auto_repair": decision.can_auto_repair,
            "blocking_codes": decision.blocking_codes,
            "repairable_codes": decision.repairable_codes,
        },
        "repaired": result.repaired,
        "issues": [_issue_to_dict(issue) for issue in result.issues],
    }


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="檢查專案啟動守門狀態")
    parser.add_argument("--project-root", default=_ROOT, help="要檢查的專案資料夾")
    parser.add_argument("--repair", action="store_true", help="執行可安全自動修復的項目")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    result = repair_project(project_root) if args.repair else inspect_project(project_root)
    decision = build_startup_decision(result)

    if args.json:
        print(json.dumps(_result_to_jsonable(result), ensure_ascii=False, indent=2))
    else:
        print(format_guard_report(result))
        print(f"啟動動作: {decision.action}")
        if not decision.can_continue:
            print("結果: blocked")

    return 0 if decision.can_continue else 2


if __name__ == "__main__":
    sys.exit(main())
