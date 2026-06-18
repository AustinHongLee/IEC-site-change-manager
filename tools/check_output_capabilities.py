# -*- coding: utf-8 -*-
"""Check workbook/PDF output capabilities for this project."""

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
from output_capabilities import build_output_capability_report


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="檢查目前輸出能力")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    ap.add_argument("--probe-com", action="store_true", help="實際啟動 Excel 探測 COM 可用性")
    ap.add_argument("--probe-libreoffice", action="store_true", help="執行 soffice --version 探測 LibreOffice")
    args = ap.parse_args()

    report = build_output_capability_report(
        probe_com_application=args.probe_com,
        probe_libreoffice_version=args.probe_libreoffice,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    summary = report["summary"]
    print(
        "輸出能力檢查："
        f" available={summary['available']}/{summary['total']}, "
        f"attention={summary['attention']}, blocking={summary['blocking']}"
    )
    for item in report["capabilities"]:
        state = "可用" if item.get("available") else "不可用"
        optional = " / optional" if item.get("optional") else ""
        print(f"- {item.get('label')} [{state}{optional}]")
        print(f"  status: {item.get('status')}")
        if item.get("reason"):
            print(f"  reason: {item.get('reason')}")
        if item.get("detail"):
            print(f"  detail: {item.get('detail')}")
    if report.get("recommendations"):
        print("建議：")
        for rec in report["recommendations"]:
            print(f"- {rec}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
