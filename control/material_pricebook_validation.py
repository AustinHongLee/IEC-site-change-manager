# -*- coding: utf-8 -*-
"""
material_pricebook_validation.py - 材料價目表驗證規則

這份是執行期與 CLI 共用的驗證核心。價目表 seed 只有通過這裡，
才允許匯入專案價目表。
"""

from __future__ import annotations

import re
from typing import Any

from console_io import configure_utf8_stdio
from material_constants import MATERIAL_ALIASES, load_material_constants, normalize_material_key


def _normalize(value: Any) -> str:
    return normalize_material_key(value)


def _parse_amount(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "").replace("，", "")
    text = re.sub(r"(?i)nt\$|ntd|twd|\$", "", text).replace("元", "").strip()
    if not text:
        return None
    try:
        float(text)
        return text
    except ValueError:
        return None


def load_controlled_vocab() -> dict[str, Any]:
    """從 material_constants 載入權威受控詞彙，回傳 normalized 集合。"""
    constants = load_material_constants()
    components = set(constants.components)
    materials = set(constants.materials)
    sizes = set(constants.sizes)
    schedules = set(constants.schedules)

    def norm_set(values):
        return {_normalize(v): v for v in values}

    return {
        "零件類型": norm_set(components),
        "材質": norm_set(materials),
        "尺寸": norm_set(sizes),
        "SCH": norm_set(schedules),
        "raw": {
            "零件類型": sorted(components),
            "材質": sorted(materials),
            "尺寸": list(constants.sizes),
            "SCH": list(constants.schedules),
        },
    }


class PricebookValidationReport:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors

    def dump(self) -> int:
        configure_utf8_stdio()
        print("─" * 60)
        for w in self.warnings:
            print(f"  ⚠️  {w}")
        for e in self.errors:
            print(f"  ❌  {e}")
        print("─" * 60)
        print(f"  WARNING: {len(self.warnings)}    ERROR: {len(self.errors)}")
        if self.errors:
            print("  ✗ 未通過。修掉所有 ERROR 後再交。")
            return 1
        print("  ✓ 通過驗證閘門。")
        return 0


# 舊工具測試與 CLI 仍沿用 Report 名稱。
Report = PricebookValidationReport


def _check_vocab(
    field: str,
    value: Any,
    vocab: dict[str, Any],
    idx: int,
    rep: PricebookValidationReport,
    *,
    allow_alias: bool = False,
    allow_empty: bool = False,
) -> None:
    raw = str(value or "").strip()
    if not raw:
        if allow_empty:
            return
        rep.err(f"第 {idx} 列：{field} 不可空白")
        return
    norm = _normalize(raw)
    if norm in vocab[field]:
        return
    if allow_alias and field == "材質" and norm in {_normalize(k) for k in MATERIAL_ALIASES}:
        canonical = MATERIAL_ALIASES[next(k for k in MATERIAL_ALIASES if _normalize(k) == norm)]
        rep.warn(
            f"第 {idx} 列：{field}=「{raw}」是別名，請統一成正規「{canonical}」"
            f"（或確認配價層已加同款 alias，否則執行期仍配不到價）"
        )
        return
    rep.err(
        f"第 {idx} 列：{field}=「{raw}」不在受控詞彙內 → 配價會靜默落空。"
        f"必須逐字使用詞彙表內字串。"
    )


def validate_pricebook_items(
    items: list[dict],
    vocab: dict[str, Any] | None = None,
    *,
    allow_price: bool,
) -> PricebookValidationReport:
    rep = PricebookValidationReport()
    if not isinstance(items, list):
        rep.err("頂層 items 必須是陣列")
        return rep

    vocab = vocab or load_controlled_vocab()
    pricebook_keys: dict[tuple, int] = {}
    ids: dict[str, int] = {}

    for i, it in enumerate(items, start=1):
        if not isinstance(it, dict):
            rep.err(f"第 {i} 列：必須是物件")
            continue

        _check_vocab("零件類型", it.get("零件類型"), vocab, i, rep)
        _check_vocab("材質", it.get("材質"), vocab, i, rep, allow_alias=True, allow_empty=True)
        _check_vocab("尺寸", it.get("尺寸"), vocab, i, rep, allow_empty=True)
        _check_vocab("SCH", it.get("SCH"), vocab, i, rep, allow_empty=True)

        if not str(it.get("單位", "")).strip():
            rep.err(f"第 {i} 列：單位 不可空白（請給預設，如『個』『M』『組』）")

        price_raw = str(it.get("單價", "")).strip()
        if allow_price:
            if price_raw and _parse_amount(price_raw) is None:
                rep.err(f"第 {i} 列：單價=「{price_raw}」不是合法數字")
        else:
            if price_raw:
                rep.err(
                    f"第 {i} 列：單價=「{price_raw}」— 規則要求留空。"
                    f"價格是合約資料，不得由模型編造。"
                )

        iid = str(it.get("id", "")).strip()
        if iid:
            if iid in ids:
                rep.err(f"第 {i} 列：id「{iid}」與第 {ids[iid]} 列重複")
            else:
                ids[iid] = i

        pk = (
            _normalize(it.get("零件類型")),
            _normalize(it.get("尺寸")),
            _normalize(it.get("SCH")),
            _normalize(it.get("材質")),
        )
        if pk[0] and pk in pricebook_keys:
            rep.err(f"第 {i} 列：與第 {pricebook_keys[pk]} 列完全重複（零件/尺寸/SCH/材質相同）")
        else:
            pricebook_keys[pk] = i

    return rep
