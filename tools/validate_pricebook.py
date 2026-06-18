# -*- coding: utf-8 -*-
"""
validate_pricebook.py — 材料價目表「驗證閘門」

用途：讓便宜模型（DeepSeek V4 Pro / Haiku 等）產出材料價目表骨架後，
在 merge 前先過這道閘門。專門擋住本專案最危險的「靜默失敗」：
價目表配價是「正規化字串相等」，零件類型/材質/尺寸/SCH 差一個字，
帶價就會悄悄落空 → 金額變 0 → 請款少算。

驗收原則：本腳本回傳 0（無 ERROR）才算通過。WARNING 不擋關，但要看。

用法：
    python tools/validate_pricebook.py <candidate.json>
    python tools/validate_pricebook.py records/material_pricebook.json --allow-price

預設規則：單價必須留空（價格是合約資料，不是常數，禁止模型編造）。
若你確定要允許帶價，加 --allow-price，改為「單價可空或為合法數字」。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# ── 路徑：腳本在 tools/ 底下，repo 根在上一層 ──
_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
CONTROL_DIR = os.path.join(_ROOT, "control")
if CONTROL_DIR not in sys.path:
    sys.path.insert(0, CONTROL_DIR)

from console_io import configure_utf8_stdio
from material_pricebook_validation import Report, load_controlled_vocab, validate_pricebook_items


configure_utf8_stdio()


def validate(items: list[dict], vocab: dict | None = None, *, allow_price: bool = False) -> Report:
    return validate_pricebook_items(items, vocab, allow_price=allow_price)


def main() -> int:
    ap = argparse.ArgumentParser(description="材料價目表驗證閘門")
    ap.add_argument("candidate", help="待驗的價目表 JSON（{items:[...]} 或直接陣列）")
    ap.add_argument("--allow-price", action="store_true", help="允許單價為空或合法數字（預設禁止帶價）")
    ap.add_argument("--list-vocab", action="store_true", help="印出受控詞彙後結束")
    args = ap.parse_args()

    vocab = load_controlled_vocab()

    if args.list_vocab:
        for k in ("零件類型", "材質", "尺寸", "SCH"):
            print(f"\n# {k}（{len(vocab['raw'][k])}）")
            for v in vocab["raw"][k]:
                print(f"  {v}")
        return 0

    with open(args.candidate, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"] if isinstance(data, dict) else data

    print(f"驗證檔案：{args.candidate}　共 {len(items)} 列")
    rep = validate(items, vocab, allow_price=args.allow_price)
    return rep.dump()


if __name__ == "__main__":
    sys.exit(main())
