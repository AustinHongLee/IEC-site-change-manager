# -*- coding: utf-8 -*-
"""
export_pricebook_template.py - 匯出材料補價表模板

預設只匯出目前價目表中「已有骨架但尚未填單價」的項目。填完單價後，
可用 tools/import_pricebook_table.py 或 GUI「匯入價格表」匯回。
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
from material_pricebook_template_exporter import export_pricebook_template_from_file


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="匯出材料補價表模板")
    ap.add_argument("output", help="輸出路徑（.xlsx / .xlsm / .csv）")
    ap.add_argument("--source", default=PRICEBOOK_JSON_PATH, help="來源 material_pricebook.json 路徑")
    ap.add_argument("--all", action="store_true", help="匯出全部價目；預設只匯出未定價項目")
    args = ap.parse_args()

    result = export_pricebook_template_from_file(
        args.output,
        source_path=args.source,
        only_unpriced=not args.all,
    )
    scope = "未定價" if result["only_unpriced"] else "全部"
    print(f"已匯出 {scope} 價目 {result['count']} 筆：{result['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
