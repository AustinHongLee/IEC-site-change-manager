# -*- coding: utf-8 -*-
"""Generate demo data and render smoke outputs."""

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


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="建立 demo 專案並產出 smoke 檔案")
    ap.add_argument("--output", default=os.path.join(_ROOT, "staging", "demo_output"), help="demo 輸出資料夾")
    ap.add_argument("--overwrite", action="store_true", help="覆寫既有 demo 輸出資料夾；只允許覆寫有 demo marker 的資料夾")
    ap.add_argument("--pdf", action="store_true", help="嘗試用 LibreOffice 轉出 PDF")
    ap.add_argument("--require-pdf", action="store_true", help="PDF 失敗時讓 smoke 失敗")
    ap.add_argument("--edge-matrix", action="store_true", help="建立 renderer edge matrix demo，不產正式輸出")
    ap.add_argument("--json", action="store_true", help="輸出 JSON result")
    args = ap.parse_args()

    if args.json:
        with contextlib.redirect_stdout(sys.stderr):
            result = _run(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = _run(args)
        _print_result(result)
    return 0 if result["ok"] else 1


def _run(args) -> dict:
    if args.edge_matrix:
        from demo_smoke import run_demo_edge_matrix

        return run_demo_edge_matrix(args.output, overwrite=args.overwrite)

    from demo_smoke import run_demo_output_smoke

    return run_demo_output_smoke(
        args.output,
        overwrite=args.overwrite,
        attempt_pdf=args.pdf or args.require_pdf,
        require_pdf=args.require_pdf,
    )


def _print_result(result: dict) -> None:
    print(f"Demo smoke：{'成功' if result.get('ok') else '失敗'}")
    print(f"專案：{result.get('project')}")
    print(f"reports：{result.get('report_count')}")
    for label, path in result.get("files", {}).items():
        if path:
            print(f"- {label}: {path}")
    pdf = result.get("pdf_conversion")
    if pdf:
        print(f"PDF：{'成功' if pdf.get('ok') else '未完成'}")
        for issue in pdf.get("issues", []):
            print(f"  [{issue.get('severity', '')}] {issue.get('code', '')}: {issue.get('message', '')}")
    for issue in result.get("issues", []):
        print(f"[{issue.get('severity', '')}] {issue.get('code', '')}: {issue.get('message', '')}")
    for case in result.get("cases", []):
        print(
            f"- {case.get('folder')}: expectation={'OK' if case.get('expectation_ok') else 'NG'} "
            f"issues={','.join(case.get('issue_codes', []))}"
        )


if __name__ == "__main__":
    sys.exit(main())
