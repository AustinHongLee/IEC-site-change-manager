# -*- coding: utf-8 -*-
"""
import_pricebook_seed.py - 安全匯入材料價目表骨架

預設只做 dry-run。必須明確加 --apply 才會寫入 records/material_pricebook.json。
匯入前會先跑 validate_pricebook；同一 (零件類型, 尺寸, SCH, 材質) 已存在時跳過，
避免 helper seed 或重跑腳本造成重複價目。
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from console_io import configure_utf8_stdio
from material_pricebook import PRICEBOOK_JSON_PATH, load_material_pricebook
from material_pricebook_importer import (
    apply_import_plan,
    build_import_plan,
    format_import_plan_summary,
    load_seed_items,
    material_key,
    validate_seed_items,
)


configure_utf8_stdio()


def _print_plan(plan: dict[str, Any], *, target: str, apply: bool) -> None:
    print(format_import_plan_summary(plan, target=target, apply=apply).replace("\n", "\n  "))


def main() -> int:
    ap = argparse.ArgumentParser(description="安全匯入材料價目表 seed")
    ap.add_argument("candidate", help="待匯入的 seed JSON（{items:[...]} 或直接陣列）")
    ap.add_argument("--target", default=PRICEBOOK_JSON_PATH, help="目標 material_pricebook.json 路徑")
    ap.add_argument("--allow-price", action="store_true", help="允許 seed 帶合法單價；預設要求單價空白")
    ap.add_argument("--apply", action="store_true", help="實際寫入目標價目表；未加時只 dry-run")
    args = ap.parse_args()

    seed_items = load_seed_items(args.candidate)
    report = validate_seed_items(seed_items, allow_price=args.allow_price)
    if report.dump() != 0:
        return 1

    current = load_material_pricebook(args.target)
    plan = build_import_plan(seed_items, current)
    _print_plan(plan, target=args.target, apply=args.apply)

    if args.apply:
        apply_import_plan(plan, current, target_path=args.target)
        print("  已寫入完成。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
