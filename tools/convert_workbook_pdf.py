# -*- coding: utf-8 -*-
"""Convert an Excel/ODS workbook to PDF with LibreOffice headless."""

from __future__ import annotations

import argparse
import json
import os
import sys


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from console_io import configure_utf8_stdio
from workbook_pdf_converter import convert_workbook_to_pdf


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="用 LibreOffice headless 將 workbook 轉成 PDF")
    ap.add_argument("workbook", help="輸入 .xlsx / .xlsm / .ods")
    ap.add_argument("output", nargs="?", default=None, help="輸出 PDF；未指定則同名 .pdf")
    ap.add_argument("--soffice", default=None, help="LibreOffice soffice 執行檔路徑；未指定則讀 settings 或自動搜尋")
    ap.add_argument("--timeout", type=int, default=120, help="轉檔逾時秒數")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    args = ap.parse_args()

    result = convert_workbook_to_pdf(
        args.workbook,
        args.output,
        soffice_path=args.soffice,
        timeout_seconds=args.timeout,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"已轉出 PDF：{result['path']}")
        print(f"  pages={result.get('pdf_validation', {}).get('pages', 0)}")
    else:
        print("workbook 轉 PDF 失敗。")
        for issue in result.get("issues", []):
            print(f"  [{issue.get('severity', '')}] {issue.get('code', '')}: {issue.get('message', '')}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
