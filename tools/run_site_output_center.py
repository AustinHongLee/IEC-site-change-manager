# -*- coding: utf-8 -*-
"""Generate formal site outputs from the project's attachments folder."""

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
    ap = argparse.ArgumentParser(description="用 attachments 建立正式現場輸出")
    ap.add_argument("--output", default=os.path.join(_ROOT, "staging", "site_output_center"), help="輸出中心資料夾")
    ap.add_argument("--project-root", default=_ROOT, help="專案根目錄")
    ap.add_argument("--attachments-root", default=None, help="attachments 根目錄；未指定時使用 project-root/attachments")
    ap.add_argument("--overwrite", action="store_true", help="覆寫既有輸出中心；只允許覆寫有 output-center marker 的資料夾")
    ap.add_argument("--no-pdf", action="store_true", help="只輸出 report_set 與統計單，不產 PDF overlay")
    ap.add_argument("--no-statistics", action="store_true", help="不輸出現場統計單 Excel")
    ap.add_argument("--no-summary-pdf", action="store_true", help="不輸出 summary PDF overlay")
    ap.add_argument("--no-photo-grid-pdf", action="store_true", help="不輸出 before/after 照片 PDF")
    ap.add_argument(
        "--report-type",
        choices=["developer", "owner-data", "both"],
        default="developer",
        help="報告型態：developer=內部檢查輸出；owner-data=業主資料包；both=兩者都產出",
    )
    ap.add_argument("--png", action="store_true", help="PDF 成功後嘗試用 Poppler 轉 PNG 供目視檢查")
    ap.add_argument("--include", action="append", default=[], metavar="DATE/FOLDER", help="只輸出指定 attachments 子資料夾，可重複指定")
    ap.add_argument("--json", action="store_true", help="輸出 JSON result")
    args = ap.parse_args()

    if args.json:
        with contextlib.redirect_stdout(sys.stderr):
            result = _run(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = _run(args)
        _print_result(result)
    return 0 if result.get("ok") else 1


def _run(args) -> dict:
    from site_output_center import run_site_output_center

    return run_site_output_center(
        args.output,
        project_root=args.project_root,
        attachments_root=args.attachments_root,
        include_report_keys=_parse_include_keys(args.include),
        overwrite=args.overwrite,
        render_pdf=not args.no_pdf,
        render_png=args.png,
        render_statistics=not args.no_statistics,
        render_summary_pdf=not args.no_summary_pdf,
        render_photo_grid_pdf=not args.no_photo_grid_pdf,
        report_type=args.report_type,
    )


def _print_result(result: dict) -> None:
    print(f"Site output center：{'成功' if result.get('ok') else '失敗'}")
    print(f"output_center：{result.get('output_center', '')}")
    print(f"reports：{result.get('report_count', 0)}")
    for label, path in result.get("files", {}).items():
        if path:
            print(f"- {label}: {path}")
    for item in result.get("renders", []):
        print(f"- PDF {item.get('folder')}: {'OK' if item.get('ok') else 'NG'} pages={item.get('pages')}")
        for code in item.get("issue_codes", []):
            print(f"  issue: {code}")
    for issue in result.get("issues", []):
        print(f"[{issue.get('report', '')}] {issue.get('code', '')}: {issue.get('message', '')}")


def _parse_include_keys(values: list[str]) -> list[tuple[str, str]] | None:
    keys = []
    for value in values or []:
        text = str(value or "").strip().replace("\\", "/")
        if "/" not in text:
            raise ValueError(f"--include 必須使用 DATE/FOLDER 格式：{value}")
        date_str, folder = text.split("/", 1)
        date_str = date_str.strip()
        folder = folder.strip()
        if not date_str or not folder:
            raise ValueError(f"--include 必須使用 DATE/FOLDER 格式：{value}")
        keys.append((date_str, folder))
    return keys or None


if __name__ == "__main__":
    sys.exit(main())
