# -*- coding: utf-8 -*-
"""
import_pricebook_table.py - 安全匯入 Excel/CSV 材料價格表

預設只做 dry-run。必須明確加 --apply 才會寫入 records/material_pricebook.json。
匯入規則：
- 新材料 key 會新增。
- 既有骨架若單價空白，會補上匯入單價。
- 既有項目已有不同單價時列為 conflict，不自動覆蓋。
"""

from __future__ import annotations

import argparse
import os
import sys


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from console_io import configure_utf8_stdio
from material_pricebook import PRICEBOOK_JSON_PATH
from material_pricebook_table_importer import (
    apply_price_table_import_plan,
    format_price_table_import_summary,
    load_and_plan_price_table_import,
)


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="安全匯入 Excel/CSV 材料價格表")
    ap.add_argument("candidate", help="待匯入的價格表（.xlsx / .xlsm / .csv）")
    ap.add_argument("--target", default=PRICEBOOK_JSON_PATH, help="目標 material_pricebook.json 路徑")
    ap.add_argument("--sheet", default=None, help="Excel 工作表名稱；未指定時使用第一個工作表")
    ap.add_argument("--apply", action="store_true", help="實際寫入目標價目表；未加時只 dry-run")
    args = ap.parse_args()

    _items, report, plan, current = load_and_plan_price_table_import(
        args.candidate,
        target_path=args.target,
        sheet_name=args.sheet,
    )
    if report.dump() != 0:
        return 1

    print(format_price_table_import_summary(plan, target=args.target, apply=args.apply).replace("\n", "\n  "))
    if args.apply:
        apply_price_table_import_plan(plan, current, target_path=args.target)
        print("  已寫入完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
