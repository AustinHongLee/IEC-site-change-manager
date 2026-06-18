# -*- coding: utf-8 -*-
"""
billing_calculator.py - 請款金額計算核心

這個模組不碰 UI、不寫檔，只負責把 records/details/materials/billing
整理成請款面板可使用的資料列。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


BILLING_CURRENCY = "TWD"
BILLING_TAX_MODE = "exclusive"
BILLING_TAX_RATE = Decimal("0.05")
BILLING_ROUNDING_RULE = "TWD_HALF_UP"
TWD_QUANT = Decimal("1")


@dataclass(frozen=True)
class ReportAmounts:
    weld_amount: Decimal = Decimal("0")
    material_amount: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return self.weld_amount + self.material_amount


def parse_amount(value: Any) -> Decimal | None:
    """解析金額/數量字串，空值或不可解析時回傳 None。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip()
    if not text:
        return None

    text = text.replace(",", "").replace("，", "")
    text = re.sub(r"(?i)nt\$|ntd|twd|\$", "", text)
    text = text.replace("元", "").strip()
    if not text:
        return None

    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def amount_to_text(value: Decimal | int | float | None) -> str:
    """轉成適合存入 JSON 的簡潔數字字串。"""
    amount = parse_amount(value)
    if amount is None:
        return ""
    if amount == 0:
        return ""
    normalized = amount.normalize()
    if normalized == normalized.to_integral():
        return str(int(normalized))
    return format(normalized, "f")


def round_twd(value: Any) -> Decimal | None:
    """請款用台幣整數進位：四捨五入到元。"""
    amount = parse_amount(value)
    if amount is None:
        return None
    return amount.quantize(TWD_QUANT, rounding=ROUND_HALF_UP)


def money_to_text(value: Any) -> str:
    """請款金額字串：套用 TWD 整數進位，0 回傳空白。"""
    amount = round_twd(value)
    if amount is None or amount == 0:
        return ""
    return str(int(amount))


def calculate_tax_amount(
    subtotal: Any,
    *,
    tax_rate: Decimal = BILLING_TAX_RATE,
) -> Decimal:
    """以未稅小計計算稅額，稅額本身也四捨五入到元。"""
    amount = round_twd(subtotal) or Decimal("0")
    return round_twd(amount * tax_rate) or Decimal("0")


def tax_rate_to_text(tax_rate: Decimal = BILLING_TAX_RATE) -> str:
    pct = tax_rate * Decimal("100")
    normalized = pct.normalize()
    if normalized == normalized.to_integral():
        return f"{int(normalized)}%"
    return f"{format(normalized, 'f')}%"


def calculate_report_amounts(store: dict[str, Any]) -> dict[str, ReportAmounts]:
    """依報告編號彙總焊口金額與材料金額。"""
    totals: dict[str, dict[str, Decimal]] = {}

    def ensure(report_id: str) -> dict[str, Decimal]:
        return totals.setdefault(report_id, {
            "weld_amount": Decimal("0"),
            "material_amount": Decimal("0"),
        })

    for detail in store.get("details", []) or []:
        if not isinstance(detail, dict):
            continue
        report_id = str(detail.get("紀錄編號") or detail.get("報告編號") or "").strip()
        if not report_id:
            continue
        amount = parse_amount(detail.get("金額")) or Decimal("0")
        ensure(report_id)["weld_amount"] += amount

    for material in store.get("materials", []) or []:
        if not isinstance(material, dict):
            continue
        report_id = str(material.get("報告編號") or "").strip()
        if not report_id:
            continue

        amount = parse_amount(material.get("金額"))
        if amount is None:
            qty = parse_amount(material.get("數量"))
            unit_price = parse_amount(material.get("單價"))
            if qty is not None and unit_price is not None:
                amount = qty * unit_price
        ensure(report_id)["material_amount"] += amount or Decimal("0")

    return {
        rid: ReportAmounts(
            weld_amount=values["weld_amount"],
            material_amount=values["material_amount"],
        )
        for rid, values in totals.items()
    }


def build_billing_rows(
    store: dict[str, Any],
    billing: dict[str, dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """
    建立請款面板資料列。

    金額來源規則：
    - 焊口/材料金額：billing.json 有手填值時保留手填值，否則自動彙總。
    - 總金額：永遠由焊口金額 + 材料金額計算，不接受獨立手填。
    - 請款層金額以 TWD 四捨五入到元；稅額預設 5% 外加。
    - 回傳的 *_source 欄位只給 UI 判斷，不會直接寫入 billing.json。
    """
    billing = billing or {}
    calculated = calculate_report_amounts(store)
    rows: list[dict[str, str]] = []

    for rec in store.get("records", []) or []:
        if not isinstance(rec, dict):
            continue
        report_id = str(rec.get("報告編號", "")).strip()
        bill = billing.get(report_id, {}) if report_id else {}
        if not isinstance(bill, dict):
            bill = {}

        calc = calculated.get(report_id, ReportAmounts())
        weld_text, weld_source = _effective_billing_amount(
            bill.get("weld_amount"), calc.weld_amount
        )
        material_text, material_source = _effective_billing_amount(
            bill.get("material_amount"), calc.material_amount
        )

        total_amount = (parse_amount(weld_text) or Decimal("0")) + (
            parse_amount(material_text) or Decimal("0")
        )
        total_text, total_source = _effective_billing_amount("", total_amount)
        subtotal_amount = parse_amount(total_text) or Decimal("0")
        tax_amount = calculate_tax_amount(subtotal_amount)
        grand_total_amount = subtotal_amount + tax_amount

        manual_total = _manual_text(bill.get("total"))
        manual_total_amount = parse_amount(manual_total)
        total_mismatch = ""
        total_mismatch_amount = ""
        if manual_total:
            if manual_total_amount is None:
                total_mismatch = "1"
            elif round_twd(manual_total_amount) != subtotal_amount:
                total_mismatch = "1"
                total_mismatch_amount = money_to_text(
                    (round_twd(manual_total_amount) or Decimal("0")) - subtotal_amount
                )

        rows.append({
            "report_id": report_id,
            "date": str(rec.get("日期", "")),
            "series": str(rec.get("Series NO", "")),
            "desc": str(rec.get("說明", "")),
            "status": str(bill.get("status", "")),
            "billing_date": str(bill.get("billing_date", "")),
            "weld_amount": weld_text,
            "weld_amount_source": weld_source,
            "material_amount": material_text,
            "material_amount_source": material_source,
            "total": total_text,
            "total_source": total_source,
            "subtotal": total_text,
            "tax_rate": tax_rate_to_text(),
            "tax_amount": money_to_text(tax_amount),
            "grand_total": money_to_text(grand_total_amount),
            "tax_mode": BILLING_TAX_MODE,
            "currency": BILLING_CURRENCY,
            "rounding_rule": BILLING_ROUNDING_RULE,
            "manual_total": manual_total,
            "total_mismatch": total_mismatch,
            "total_mismatch_amount": total_mismatch_amount,
            "remark": str(bill.get("remark", "")),
        })

    return rows


def _manual_text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text


def _effective_amount(manual_value: Any, calculated_value: Decimal) -> tuple[str, str]:
    manual_text = _manual_text(manual_value)
    if manual_text:
        return manual_text, "manual"
    if calculated_value:
        return amount_to_text(calculated_value), "calculated"
    return "", "empty"


def _effective_billing_amount(manual_value: Any, calculated_value: Decimal) -> tuple[str, str]:
    manual_text = _manual_text(manual_value)
    if manual_text:
        rounded = money_to_text(manual_text)
        if rounded:
            return rounded, "manual"
        if parse_amount(manual_text) == Decimal("0"):
            return "", "manual"
        return manual_text, "manual_invalid"
    if calculated_value:
        return money_to_text(calculated_value), "calculated"
    return "", "empty"
