# -*- coding: utf-8 -*-
"""
render_xlsx_template.py - 以 xlsx_template JSON 產出單張 CanonicalReport Excel。
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
from output_result import attach_output_envelope, output_item, step_item
from renderer_registry import render_with_template
from workbook_pdf_converter import convert_workbook_to_pdf


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="用 xlsx_template JSON 渲染單張修改單 Excel")
    ap.add_argument("template", help="template JSON")
    ap.add_argument("output", help="輸出 .xlsx 路徑")
    ap.add_argument("--report-set", default=None, help="可選：CanonicalReportSet JSON；未指定則掃目前專案")
    ap.add_argument("--report", default=None, help="指定 report_id 或資料夾名；未指定使用第一筆")
    ap.add_argument("--pdf-output", default=None, help="可選：xlsx 渲染成功後轉出的 PDF 路徑")
    ap.add_argument("--soffice", default=None, help="可選：LibreOffice soffice.exe 路徑；未指定則讀 settings 或自動搜尋")
    ap.add_argument("--pdf-timeout", type=int, default=120, help="LibreOffice PDF 轉檔逾秒時間")
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
    _maybe_convert_pdf(
        result,
        args.output,
        args.pdf_output,
        soffice_path=args.soffice,
        timeout_seconds=args.pdf_timeout,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_result(args.output, result)
    return 0 if result["ok"] else 1


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


def _maybe_convert_pdf(
    result: dict,
    workbook_path: str,
    pdf_output: str | None,
    *,
    soffice_path: str | None,
    timeout_seconds: int,
) -> None:
    if not pdf_output:
        return
    if not result.get("ok"):
        result["pdf_conversion"] = {
            "ok": False,
            "skipped": True,
            "reason": "xlsx_template render failed",
            "issues": [],
        }
        return

    pdf_result = convert_workbook_to_pdf(
        workbook_path,
        pdf_output,
        soffice_path=soffice_path,
        timeout_seconds=timeout_seconds,
    )
    result["pdf_conversion"] = pdf_result
    _refresh_envelope_after_pdf(result, pdf_result)
    if pdf_result.get("ok"):
        return

    result["ok"] = False
    result.setdefault("issues", []).extend(pdf_result.get("issues", []))
    _refresh_envelope_after_pdf(result, pdf_result)


def _print_result(output_path: str, result: dict) -> None:
    pdf_conversion = result.get("pdf_conversion")
    workbook_exists = os.path.exists(output_path)
    if not result["ok"] and not (pdf_conversion and workbook_exists):
        print("xlsx_template 渲染失敗。")
    else:
        summary = result.get("summary", {})
        print(f"已渲染 xlsx_template：{output_path}")
        print(
            f"  text={summary.get('text', 0)}, image={summary.get('image', 0)}, "
            f"table={summary.get('table', 0)}, rows={summary.get('rows', 0)}"
        )
    if pdf_conversion:
        if pdf_conversion.get("ok"):
            print(f"已轉出 PDF：{pdf_conversion.get('path', '')}")
        elif pdf_conversion.get("skipped"):
            print("PDF 轉檔略過：xlsx_template 渲染未成功。")
        else:
            print("PDF 轉檔失敗。")
    for issue in result.get("issues", []):
        print(f"  [{issue.get('severity', '')}] {issue.get('code', '')}: {issue.get('message', '')}")


def _refresh_envelope_after_pdf(result: dict, pdf_result: dict) -> None:
    outputs = list(result.get("outputs", []) or [])
    if pdf_result.get("ok"):
        outputs.append(output_item(kind="pdf", path=pdf_result.get("path", ""), role="pdf", label="PDF"))
    steps = list(result.get("steps", []) or [])
    steps.append(
        step_item(
            key="workbook_pdf_conversion",
            ok=pdf_result.get("ok", False),
            label="Convert workbook to PDF",
        )
    )
    capabilities = dict(result.get("capabilities", {}) or {})
    capabilities["pdf_conversion"] = pdf_result.get("capability", {})
    attach_output_envelope(result, outputs=outputs, capabilities=capabilities, steps=steps)


if __name__ == "__main__":
    sys.exit(main())
