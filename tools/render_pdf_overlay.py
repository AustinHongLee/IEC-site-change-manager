# -*- coding: utf-8 -*-
"""Render one CanonicalReport with a pdf_overlay template."""

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
from renderer_registry import render_with_template


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="用 pdf_overlay JSON 渲染單張修改單 PDF")
    ap.add_argument("template", help="pdf_overlay template JSON")
    ap.add_argument("output", help="輸出 PDF 路徑")
    ap.add_argument("--report-set", default=None, help="可選：CanonicalReportSet JSON；未指定則掃目前專案")
    ap.add_argument("--report", default=None, help="指定 report_id 或資料夾名；未指定使用第一筆")
    ap.add_argument("--json", action="store_true", help="輸出 JSON render result")
    args = ap.parse_args()

    with open(args.template, "r", encoding="utf-8") as f:
        template = json.load(f)
    report_set = _load_report_set(args.report_set, quiet_stdout=args.json)
    report = _select_report(report_set, args.report)
    if report is None:
        print("找不到可渲染的 report。")
        return 1

    result = render_with_template(
        report,
        template,
        args.output,
        template_dir=os.path.dirname(os.path.abspath(args.template)),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_result(result)
    return 0 if result.get("ok") else 1


def _load_report_set(path: str | None, *, quiet_stdout: bool = False) -> dict:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    if quiet_stdout:
        with contextlib.redirect_stdout(sys.stderr):
            from canonical_report import collect_canonical_report_set
            return collect_canonical_report_set()
    from canonical_report import collect_canonical_report_set
    return collect_canonical_report_set()


def _select_report(report_set: dict, report_label: str | None) -> dict | None:
    reports = report_set.get("reports", []) or []
    if not reports:
        return None
    if not report_label:
        return reports[0]
    needle = str(report_label).strip()
    for report in reports:
        info = report.get("report", {})
        if needle in {str(info.get("report_id", "")).strip(), str(info.get("folder", "")).strip()}:
            return report
    return None


def _print_result(result: dict) -> None:
    if result.get("ok"):
        print(f"已渲染 pdf_overlay：{result.get('path', '')}")
    else:
        print("pdf_overlay 渲染失敗。")
    summary = result.get("summary", {})
    print(
        f"  text={summary.get('text', 0)}, image={summary.get('image', 0)}, "
        f"table={summary.get('table', 0)}, rows={summary.get('rows', 0)}"
    )
    for issue in result.get("issues", []):
        print(f"  [{issue.get('severity', '')}] {issue.get('code', '')}: {issue.get('message', '')}")


if __name__ == "__main__":
    sys.exit(main())
