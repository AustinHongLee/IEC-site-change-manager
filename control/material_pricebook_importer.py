# -*- coding: utf-8 -*-
"""
material_pricebook_importer.py - 材料價目表 seed 安全匯入核心

CLI 與 GUI 共用此模組，確保匯入規則一致：先驗證、再產生 dry-run 摘要，
只有確認後才寫入，且不覆蓋既有材料 key。
"""

from __future__ import annotations

import json
from typing import Any

from material_constants import normalize_material_key
from material_pricebook import load_material_pricebook, normalize_pricebook_items, save_material_pricebook
from material_pricebook_validation import PricebookValidationReport, validate_pricebook_items


PRICEBOOK_KEY_FIELDS = ("零件類型", "尺寸", "SCH", "材質")


def load_seed_items(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("seed JSON 必須是 {items:[...]} 或直接陣列")
    return [dict(item) for item in items if isinstance(item, dict)]


def material_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(normalize_material_key(item.get(field)) for field in PRICEBOOK_KEY_FIELDS)


def validate_seed_items(seed_items: list[dict[str, Any]], *, allow_price: bool = False) -> PricebookValidationReport:
    return validate_pricebook_items(seed_items, allow_price=allow_price)


def build_import_plan(seed_items: list[dict[str, Any]], current_pricebook: dict[str, Any]) -> dict[str, Any]:
    current_items = normalize_pricebook_items(current_pricebook.get("items", []))
    seed_normalized = normalize_pricebook_items(seed_items)
    known_keys = {material_key(item) for item in current_items if item.get("零件類型")}
    added: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for item in seed_normalized:
        key = material_key(item)
        if key in known_keys:
            skipped.append(item)
            continue
        known_keys.add(key)
        added.append(item)

    return {
        "items": current_items + added,
        "added": added,
        "skipped": skipped,
        "existing_count": len(current_items),
        "candidate_count": len(seed_normalized),
    }


def format_import_plan_summary(plan: dict[str, Any], *, apply: bool = False, target: str = "") -> str:
    mode = "APPLY" if apply else "DRY-RUN"
    lines = [f"[{mode}]"]
    if target:
        lines.append(f"目標價目表: {target}")
    lines.extend([
        f"既有項目: {plan['existing_count']}",
        f"seed 項目: {plan['candidate_count']}",
        f"將新增: {len(plan['added'])}",
        f"已存在略過: {len(plan['skipped'])}",
    ])
    if not apply:
        lines.append("尚未寫入；確認後才會更新目標價目表。")
    return "\n".join(lines)


def apply_import_plan(
    plan: dict[str, Any],
    current_pricebook: dict[str, Any],
    *,
    target_path: str | None = None,
) -> None:
    merged = dict(current_pricebook)
    merged["items"] = plan["items"]
    save_material_pricebook(merged, target_path)


def load_and_plan_seed_import(
    seed_path: str,
    *,
    target_path: str | None = None,
    allow_price: bool = False,
) -> tuple[list[dict[str, Any]], PricebookValidationReport, dict[str, Any], dict[str, Any]]:
    seed_items = load_seed_items(seed_path)
    report = validate_seed_items(seed_items, allow_price=allow_price)
    current = load_material_pricebook(target_path)
    plan = build_import_plan(seed_items, current) if report.ok else {
        "items": current.get("items", []),
        "added": [],
        "skipped": [],
        "existing_count": len(current.get("items", [])),
        "candidate_count": len(seed_items),
    }
    return seed_items, report, plan, current
