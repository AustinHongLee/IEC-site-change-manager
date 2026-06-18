# -*- coding: utf-8 -*-
"""
validate_template.py - 驗證輸出模板 mapping 是否只引用 CanonicalReport 欄位。
"""

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
from canonical_fields import list_field_paths
from template_mapping import validate_template_mapping


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="驗證輸出模板 mapping")
    ap.add_argument("candidate", help="待驗證 template JSON")
    ap.add_argument("--list-fields", action="store_true", help="印出 field-path catalog 後結束")
    args = ap.parse_args()

    if args.list_fields:
        for field in list_field_paths():
            print(field)
        return 0

    with open(args.candidate, "r", encoding="utf-8") as f:
        template = json.load(f)

    report = validate_template_mapping(template)
    print(f"驗證模板：{args.candidate}")
    print(f"  fields: {report['field_count']}")
    for warning in report["warnings"]:
        print(f"  WARNING: {warning}")
    for error in report["errors"]:
        print(f"  ERROR: {error}")
    if report["ok"]:
        print("  通過模板驗證。")
        return 0
    print("  未通過模板驗證。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
