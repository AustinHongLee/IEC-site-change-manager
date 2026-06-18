# -*- coding: utf-8 -*-
"""
export_site_statistics.py - 匯出現場修改統計單
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
from workbook_pdf_converter import convert_workbook_to_pdf


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="匯出現場修改統計單")
    ap.add_argument("--output", default=None, help="輸出 .xlsx 路徑；未指定時輸出到 records/")
    ap.add_argument("--pdf-output", default=None, help="可選：xlsx 匯出成功後轉出的 PDF 路徑")
    ap.add_argument("--soffice", default=None, help="可選：LibreOffice soffice.exe 路徑；未指定則讀 settings 或自動搜尋")
    ap.add_argument("--pdf-timeout", type=int, default=120, help="LibreOffice PDF 轉檔逾秒時間")
    ap.add_argument("--json", action="store_true", help="輸出 JSON result")
    args = ap.parse_args()

    if args.json:
        with contextlib.redirect_stdout(sys.stderr):
            from site_statistics_exporter import export_site_statistics_workbook
            path = export_site_statistics_workbook(args.output)
    else:
        from site_statistics_exporter import export_site_statistics_workbook
        path = export_site_statistics_workbook(args.output)
    result = {
        "ok": True,
        "xlsx": path,
        "pdf_conversion": None,
        "issues": [],
    }
    attach_output_envelope(
        result,
        outputs=[output_item(kind="site_statistics_xlsx", path=path, role="primary", label="現場修改統計單 Excel")],
        steps=[step_item(key="site_statistics_export", ok=True, label="Export site statistics workbook")],
    )
    if args.pdf_output:
        pdf_result = convert_workbook_to_pdf(
            path,
            args.pdf_output,
            soffice_path=args.soffice,
            timeout_seconds=args.pdf_timeout,
        )
        result["pdf_conversion"] = pdf_result
        if not pdf_result.get("ok"):
            result["ok"] = False
            result["issues"].extend(pdf_result.get("issues", []))
        _refresh_envelope_after_pdf(result, pdf_result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_result(result)
    return 0 if result["ok"] else 1


def _print_result(result: dict) -> None:
    print(f"已匯出現場修改統計單：{result.get('xlsx', '')}")
    pdf_result = result.get("pdf_conversion")
    if pdf_result:
        if pdf_result.get("ok"):
            print(f"已轉出 PDF：{pdf_result.get('path', '')}")
        else:
            print("PDF 轉檔失敗。")
    for issue in result.get("issues", []):
        print(f"  [{issue.get('severity', '')}] {issue.get('code', '')}: {issue.get('message', '')}")


def _refresh_envelope_after_pdf(result: dict, pdf_result: dict) -> None:
    outputs = list(result.get("outputs", []) or [])
    if pdf_result.get("ok"):
        outputs.append(output_item(kind="pdf", path=pdf_result.get("path", ""), role="pdf", label="PDF"))
    steps = list(result.get("steps", []) or [])
    steps.append(step_item(key="workbook_pdf_conversion", ok=pdf_result.get("ok", False), label="Convert workbook to PDF"))
    capabilities = dict(result.get("capabilities", {}) or {})
    capabilities["pdf_conversion"] = pdf_result.get("capability", {})
    attach_output_envelope(result, outputs=outputs, capabilities=capabilities, steps=steps)


if __name__ == "__main__":
    sys.exit(main())
