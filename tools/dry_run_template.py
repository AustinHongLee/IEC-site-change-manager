# -*- coding: utf-8 -*-
"""
dry_run_template.py - 用 CanonicalReportSet 預覽 template mapping 會如何取值。
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from console_io import configure_utf8_stdio
from template_dry_run import dry_run_template_for_report_set


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="預覽輸出模板 dry-run，不產生 Excel/PDF")
    ap.add_argument("template", help="template JSON")
    ap.add_argument("--report-set", default=None, help="可選：已匯出的 CanonicalReportSet JSON")
    ap.add_argument("--json", action="store_true", help="輸出 JSON 結果")
    args = ap.parse_args()

    with open(args.template, "r", encoding="utf-8") as f:
        template = json.load(f)
    if args.report_set:
        with open(args.report_set, "r", encoding="utf-8") as f:
            report_set = json.load(f)
    else:
        if args.json:
            with contextlib.redirect_stdout(sys.stderr):
                from canonical_report import collect_canonical_report_set
                report_set = collect_canonical_report_set()
        else:
            from canonical_report import collect_canonical_report_set
            report_set = collect_canonical_report_set()

    result = dry_run_template_for_report_set(report_set, template)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human_report(args.template, result)
    return 0 if result["ok"] else 1


def _print_human_report(template_path: str, result: dict) -> None:
    print(f"DRY-RUN template: {template_path}")
    print(f"  reports: {result['summary']['report_count']}")
    print(f"  issues: {result['summary']['issue_count']}")
    for report_result in result.get("reports", []):
        summary = report_result.get("summary", {})
        report_label = report_result.get("report") or "<未命名>"
        print(
            f"- {report_label}: fields={summary.get('field_count', 0)}, "
            f"text={summary.get('text_count', 0)}, image={summary.get('image_count', 0)}, "
            f"table={summary.get('table_count', 0)}, issues={summary.get('issue_count', 0)}"
        )
        for issue in report_result.get("issues", []):
            print(f"  [{issue.get('severity', '')}] {issue.get('code', '')}: {issue.get('message', '')}")


if __name__ == "__main__":
    sys.exit(main())
