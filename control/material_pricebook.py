# -*- coding: utf-8 -*-
"""
material_pricebook.py - 專案材料價目表

v1 先採用每個專案一份簡單 JSON：
records/material_pricebook.json

價目表只提供預設單價；寫入修改單材料明細時會拍照成當下單價，
之後修改價目表不會回頭改變既有單據。
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from billing_calculator import amount_to_text, parse_amount
from material_constants import (
    MATERIAL_FIELD_COMPONENT,
    MATERIAL_FIELD_MATERIAL,
    MATERIAL_FIELD_SCH,
    MATERIAL_FIELD_SIZE,
    canonicalize_material_row,
    canonicalize_material_value,
    material_default_unit,
    normalize_material_key,
)
from utils import atomic_write_json
from resources import project_path


PRICEBOOK_JSON_PATH = project_path("records", "material_pricebook.json")
PRICE_SOURCE_MISSING = "missing_pricebook"
PRICE_SOURCE_MISSING_PRICE = "missing_price"
AMOUNT_SOURCE_MISSING = "missing_price"
PRICEBOOK_VERSION = "1.1"


DEFAULT_PRICEBOOK: dict[str, Any] = {
    "items": [],
    "history": [],
    "meta": {
        "version": PRICEBOOK_VERSION,
        "currency": "TWD",
        "notes": "空白價目表；可逐步加入專案合約材料單價。",
    },
}


@dataclass(frozen=True)
class MaterialPriceMatch:
    item: dict[str, Any]
    unit_price: Decimal | None
    source_id: str
    unit: str
    score: int


def load_material_pricebook(path: str | None = None) -> dict[str, Any]:
    """載入材料價目表。檔案不存在時回傳空白價目表。"""
    path = path or PRICEBOOK_JSON_PATH
    if not os.path.exists(path):
        return copy.deepcopy(DEFAULT_PRICEBOOK)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_PRICEBOOK)
    if not isinstance(data.get("items"), list):
        data["items"] = []
    if not isinstance(data.get("history"), list):
        data["history"] = []
    data.setdefault("meta", copy.deepcopy(DEFAULT_PRICEBOOK["meta"]))
    return data


def save_material_pricebook(pricebook: dict[str, Any], path: str | None = None) -> None:
    """原子寫入材料價目表。"""
    path = path or PRICEBOOK_JSON_PATH
    previous = load_material_pricebook(path) if os.path.exists(path) else copy.deepcopy(DEFAULT_PRICEBOOK)
    data = copy.deepcopy(pricebook)
    items = data.get("items")
    if not isinstance(items, list):
        items = []
    normalized_items = [_normalize_pricebook_item(item) for item in items if isinstance(item, dict)]
    previous_items = normalize_pricebook_items(previous.get("items", []))
    data["items"] = normalized_items
    data["history"] = _normalize_pricebook_history(previous.get("history", []))
    data["history"].extend(_build_pricebook_history(previous_items, normalized_items))
    meta = data.setdefault("meta", copy.deepcopy(DEFAULT_PRICEBOOK["meta"]))
    meta["version"] = PRICEBOOK_VERSION
    meta["currency"] = str(meta.get("currency") or "TWD")
    meta["last_modified"] = datetime.now().isoformat(timespec="seconds")
    atomic_write_json(path, data)


def normalize_pricebook_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """將 UI 或匯入資料正規化成價目表列。"""
    return [_normalize_pricebook_item(item) for item in items if isinstance(item, dict)]


def find_material_price(
    material_row: dict[str, Any],
    pricebook: dict[str, Any] | None,
) -> MaterialPriceMatch | None:
    """依材料列尋找最適合的價目表單價。"""
    if not pricebook:
        return None

    material_row = canonicalize_material_row(material_row)
    target_component = _field(material_row, "零件類型", "component", "name")
    if not target_component:
        return None

    best: MaterialPriceMatch | None = None
    for item in pricebook.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        item = _normalize_pricebook_item(item)

        component = _field(item, "零件類型", "component", "name")
        if not component or _normalize(component) != _normalize(target_component):
            continue

        unit_price = parse_amount(_field(item, "單價", "unit_price", "price"))

        score = 100
        if not _matches_optional(item, material_row, ("尺寸", "size"), 12):
            continue
        score += _match_score(item, ("尺寸", "size"), 12)

        if not _matches_optional(item, material_row, ("SCH", "schedule", "sch"), 6):
            continue
        score += _match_score(item, ("SCH", "schedule", "sch"), 6)

        if not _matches_optional(item, material_row, ("材質", "material"), 4):
            continue
        score += _match_score(item, ("材質", "material"), 4)

        source_id = _field(item, "id", "料號", "material_id") or _make_source_id(item)
        unit = _field(item, "單位", "unit") or ""
        match = MaterialPriceMatch(item=item, unit_price=unit_price, source_id=source_id, unit=unit, score=score)
        if best is None or match.score > best.score or (
            match.score == best.score and best.unit_price is None and match.unit_price is not None
        ):
            best = match

    return best


def apply_material_pricing(
    material_rows: list[dict[str, Any]],
    pricebook: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """將價目表單價套用到材料列，並計算金額。"""
    pricebook = pricebook if pricebook is not None else load_material_pricebook()
    priced_rows: list[dict[str, Any]] = []

    for row in material_rows:
        out = canonicalize_material_row(dict(row))
        if not str(out.get("類別", "")).strip():
            out["類別"] = "材料"
        qty = parse_amount(out.get("數量"))
        unit_price = parse_amount(out.get("單價"))
        amount = parse_amount(out.get("金額"))

        if unit_price is None:
            match = find_material_price(out, pricebook)
            if match:
                out["價目表ID"] = match.source_id
                out["類別"] = _field(match.item, "類別", "category") or out.get("類別", "材料")
                out["價目來源"] = _field(match.item, "來源", "source")
                out["價目生效日"] = _field(match.item, "生效日", "effective_date", "effective_from")
                if match.unit and not str(out.get("單位", "")).strip():
                    out["單位"] = match.unit
                if match.unit_price is not None:
                    unit_price = match.unit_price
                    out["單價"] = amount_to_text(unit_price)
                    out["單價來源"] = "pricebook"
                    out["配價狀態"] = "matched"
                else:
                    out["單價"] = ""
                    out["單價來源"] = PRICE_SOURCE_MISSING_PRICE
                    out["配價狀態"] = PRICE_SOURCE_MISSING_PRICE
            elif _field(out, "零件類型", "component", "name"):
                out["單價"] = ""
                out["單價來源"] = PRICE_SOURCE_MISSING
                out["價目表ID"] = ""
                out["價目來源"] = ""
                out["價目生效日"] = ""
                out["配價狀態"] = PRICE_SOURCE_MISSING
        elif not str(out.get("單價來源", "")).strip():
            out["單價來源"] = "manual"
            out["配價狀態"] = "manual"

        if amount is None and qty is not None and unit_price is not None:
            out["金額"] = amount_to_text(qty * unit_price)
            out["金額來源"] = "calculated"
        elif amount is None and out.get("單價來源") in (PRICE_SOURCE_MISSING, PRICE_SOURCE_MISSING_PRICE):
            out["金額"] = ""
            out["金額來源"] = AMOUNT_SOURCE_MISSING
        elif amount is not None and not str(out.get("金額來源", "")).strip():
            out["金額來源"] = "manual"

        priced_rows.append(out)

    return priced_rows


def unresolved_material_price_status(material_row: dict[str, Any]) -> str:
    """回傳未解決配價狀態；空字串代表已可計價或不需提示。"""
    if not isinstance(material_row, dict):
        return ""
    if not _field(material_row, "零件類型", "component", "name"):
        return ""
    if parse_amount(_field(material_row, "單價", "unit_price", "price")) is not None:
        return ""
    source = _field(material_row, "單價來源", "price_source")
    status = _field(material_row, "配價狀態", "pricing_status")
    if source == PRICE_SOURCE_MISSING_PRICE or status == PRICE_SOURCE_MISSING_PRICE:
        return PRICE_SOURCE_MISSING_PRICE
    if source == PRICE_SOURCE_MISSING or status == PRICE_SOURCE_MISSING:
        return PRICE_SOURCE_MISSING
    return ""


def unresolved_material_counts_by_report(material_rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in material_rows or []:
        if not isinstance(row, dict):
            continue
        report_id = _field(row, "報告編號", "report_id")
        if not report_id:
            continue
        status = unresolved_material_price_status(row)
        if not status:
            continue
        bucket = counts.setdefault(report_id, {
            "total": 0,
            PRICE_SOURCE_MISSING_PRICE: 0,
            PRICE_SOURCE_MISSING: 0,
        })
        bucket["total"] += 1
        bucket[status] += 1
    return counts


def _field(data: dict[str, Any], *names: str) -> str:
    for name in names:
        value = data.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize(value: Any) -> str:
    return normalize_material_key(value)


def _matches_optional(
    price_item: dict[str, Any],
    material_row: dict[str, Any],
    names: tuple[str, ...],
    _score: int,
) -> bool:
    expected = _field(price_item, *names)
    if not expected:
        return True
    actual = _field(material_row, *names)
    return bool(actual) and _normalize(actual) == _normalize(expected)


def _match_score(price_item: dict[str, Any], names: tuple[str, ...], score: int) -> int:
    return score if _field(price_item, *names) else 0


def _make_source_id(item: dict[str, Any]) -> str:
    parts = [
        _field(item, "零件類型", "component", "name"),
        _field(item, "尺寸", "size"),
        _field(item, "SCH", "schedule", "sch"),
        _field(item, "材質", "material"),
    ]
    return "|".join(p for p in parts if p) or "pricebook"


def _normalize_pricebook_item(item: dict[str, Any]) -> dict[str, str]:
    component = canonicalize_material_value(MATERIAL_FIELD_COMPONENT, _field(item, "零件類型", "component", "name"))
    size = canonicalize_material_value(MATERIAL_FIELD_SIZE, _field(item, "尺寸", "size"))
    sch = canonicalize_material_value(MATERIAL_FIELD_SCH, _field(item, "SCH", "schedule", "sch"))
    material = canonicalize_material_value(MATERIAL_FIELD_MATERIAL, _field(item, "材質", "material"))
    unit = _field(item, "單位", "unit") or material_default_unit(component)
    normalized = {
        "id": _field(item, "id", "料號", "material_id"),
        "零件類型": component,
        "尺寸": size,
        "SCH": sch,
        "材質": material,
        "類別": _field(item, "類別", "category") or "材料",
        "單位": unit,
        "單價": amount_to_text(parse_amount(_field(item, "單價", "unit_price", "price"))),
        "來源": _field(item, "來源", "source", "price_source") or "合約",
        "生效日": _normalize_effective_date(_field(item, "生效日", "effective_date", "effective_from")),
        "備註": _field(item, "備註", "remark", "notes"),
    }
    if not normalized["id"]:
        normalized["id"] = _make_source_id(normalized)
    return normalized


def _normalize_effective_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return text


def _normalize_pricebook_history(history: Any) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    return [dict(item) for item in history if isinstance(item, dict)]


def _build_pricebook_history(
    previous_items: list[dict[str, str]],
    current_items: list[dict[str, str]],
) -> list[dict[str, str]]:
    previous_by_id = {item.get("id", ""): item for item in previous_items if item.get("id")}
    current_by_id = {item.get("id", ""): item for item in current_items if item.get("id")}
    now = datetime.now().isoformat(timespec="seconds")
    events: list[dict[str, str]] = []

    for item_id, current in current_by_id.items():
        previous = previous_by_id.get(item_id)
        if not previous:
            continue
        if (
            previous.get("單價", "") != current.get("單價", "")
            or previous.get("來源", "") != current.get("來源", "")
            or previous.get("生效日", "") != current.get("生效日", "")
        ):
            events.append({
                "event": "price_changed",
                "changed_at": now,
                "id": item_id,
                "零件類型": current.get("零件類型", ""),
                "尺寸": current.get("尺寸", ""),
                "SCH": current.get("SCH", ""),
                "材質": current.get("材質", ""),
                "類別": current.get("類別", ""),
                "old_price": previous.get("單價", ""),
                "new_price": current.get("單價", ""),
                "old_source": previous.get("來源", ""),
                "new_source": current.get("來源", ""),
                "old_effective_date": previous.get("生效日", ""),
                "new_effective_date": current.get("生效日", ""),
            })

    for item_id, previous in previous_by_id.items():
        if item_id not in current_by_id:
            events.append({
                "event": "removed",
                "changed_at": now,
                "id": item_id,
                "零件類型": previous.get("零件類型", ""),
                "尺寸": previous.get("尺寸", ""),
                "SCH": previous.get("SCH", ""),
                "材質": previous.get("材質", ""),
                "類別": previous.get("類別", ""),
                "old_price": previous.get("單價", ""),
                "old_source": previous.get("來源", ""),
                "old_effective_date": previous.get("生效日", ""),
            })

    return events
