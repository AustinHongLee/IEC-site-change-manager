# -*- coding: utf-8 -*-
"""
Run a compact release smoke for startup guard, integrity audit, and output center.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from console_io import configure_utf8_stdio
from integrity_audit import audit_integrity
from project_guard import build_startup_decision, inspect_project, repair_project


def _issue_to_dict(issue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "title": issue.title,
        "message": issue.message,
        "refs": list(getattr(issue, "refs", []) or []),
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


def run_release_smoke(
    project_root: str | Path,
    *,
    output_dir: str | Path | None = None,
    repair: bool = False,
    render_pdf: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    output = Path(output_dir).resolve() if output_dir else root / "staging" / "release_smoke"

    guard = repair_project(root) if repair else inspect_project(root)
    decision = build_startup_decision(guard)
    result: dict[str, Any] = {
        "ok": False,
        "project_root": str(root),
        "output_dir": str(output),
        "startup": {
            "state": guard.state,
            "decision": {
                "action": decision.action,
                "title": decision.title,
                "can_continue": decision.can_continue,
                "can_auto_repair": decision.can_auto_repair,
            },
            "repaired": guard.repaired,
            "issues": [_guard_issue_to_dict(issue) for issue in guard.issues],
        },
        "integrity": None,
        "output_center": None,
    }

    if not decision.can_continue:
        result["reason"] = "startup_blocked"
        return result

    integrity = audit_integrity(root)
    severity = integrity.count_by_severity()
    result["integrity"] = {
        "ok": not integrity.has_errors,
        "counts": integrity.counts,
        "severity": severity,
        "issues": [_issue_to_dict(issue) for issue in integrity.issues],
    }
    if integrity.has_errors:
        result["reason"] = "integrity_errors"
        return result

    with contextlib.redirect_stdout(io.StringIO()):
        from site_output_center import run_site_output_center

        output_result = run_site_output_center(
            str(output),
            project_root=str(root),
            attachments_root=str(root / "attachments"),
            overwrite=True,
            render_pdf=render_pdf,
            render_png=False,
            render_statistics=True,
            render_summary_pdf=render_pdf,
            render_photo_grid_pdf=render_pdf,
        )

    result["output_center"] = output_result
    result["ok"] = bool(output_result.get("ok"))
    if not result["ok"]:
        result["reason"] = "output_center_failed"
    return result


def _print_text(result: dict[str, Any]) -> None:
    print(f"Release smoke：{'成功' if result.get('ok') else '失敗'}")
    print(f"project_root：{result.get('project_root')}")
    print(f"output_dir：{result.get('output_dir')}")
    startup = result.get("startup") or {}
    decision = startup.get("decision") or {}
    print(f"startup：{decision.get('action')} - {decision.get('title')}")
    integrity = result.get("integrity") or {}
    if integrity:
        severity = integrity.get("severity") or {}
        print(
            "integrity："
            f"error={severity.get('error', 0)}, "
            f"warning={severity.get('warning', 0)}, "
            f"info={severity.get('info', 0)}"
        )
    output = result.get("output_center") or {}
    if output:
        print(f"output_center：{'OK' if output.get('ok') else 'NG'} reports={output.get('report_count', 0)}")
        for label, path in (output.get("files") or {}).items():
            if path:
                print(f"- {label}: {path}")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="執行 release smoke")
    parser.add_argument("--project-root", default=_ROOT, help="專案根目錄")
    parser.add_argument("--output", default="", help="release smoke 輸出資料夾")
    parser.add_argument("--repair", action="store_true", help="先執行安全自動修復")
    parser.add_argument("--pdf", action="store_true", help="同時產出 PDF overlay")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args()

    result = run_release_smoke(
        args.project_root,
        output_dir=args.output or None,
        repair=args.repair,
        render_pdf=args.pdf,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
