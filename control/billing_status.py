# -*- coding: utf-8 -*-
"""
billing_status.py - 請款狀態 enum 與狀態機

狀態規則集中在這裡，避免 UI、材料鎖定、未來請款批次各自解讀。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


UNBILLED = "未請款"

BILLING_STATUS_OPTIONS = (
    UNBILLED,
    "請款中",
    "已請款",
    "部分付款",
    "已付款",
    "補件中",
    "退回",
    "已結案",
    "暫緩",
    "作廢",
)

BILLING_STATUS_SET = set(BILLING_STATUS_OPTIONS)

LOCKED_BILLING_STATUSES = {
    "請款中",
    "已請款",
    "部分付款",
    "已付款",
    "補件中",
    "退回",
    "已結案",
}

ALLOWED_TRANSITIONS = {
    UNBILLED: {UNBILLED, "請款中", "暫緩", "作廢"},
    "暫緩": {UNBILLED, "暫緩", "請款中", "作廢"},
    "請款中": {"請款中", "已請款", "補件中", "退回", "作廢"},
    "補件中": {"補件中", "請款中", "退回", "作廢"},
    "退回": {"退回", "補件中", "請款中", "作廢"},
    "已請款": {"已請款", "部分付款", "已付款", "補件中", "退回", "已結案"},
    "部分付款": {"部分付款", "已付款", "補件中", "已結案"},
    "已付款": {"已付款", "已結案"},
    "已結案": {"已結案"},
    "作廢": {"作廢"},
}


@dataclass(frozen=True)
class BillingStatusIssue:
    report_id: str
    old_status: str
    new_status: str
    message: str


def normalize_billing_status(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text or UNBILLED


def is_valid_billing_status(value: Any) -> bool:
    return normalize_billing_status(value) in BILLING_STATUS_SET


def is_billing_locked(value: Any) -> bool:
    return normalize_billing_status(value) in LOCKED_BILLING_STATUSES


def validate_billing_transition(old_value: Any, new_value: Any) -> str | None:
    old_status = normalize_billing_status(old_value)
    new_status = normalize_billing_status(new_value)
    if new_status not in BILLING_STATUS_SET:
        return f"請款狀態「{new_status}」不是系統允許的狀態"
    if old_status not in BILLING_STATUS_SET:
        return None
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, {old_status}):
        return f"請款狀態不可由「{old_status}」直接改為「{new_status}」"
    return None


def validate_billing_status_changes(
    old_billing: dict[str, dict[str, Any]] | None,
    new_billing: dict[str, dict[str, Any]] | None,
) -> list[BillingStatusIssue]:
    old_billing = old_billing or {}
    new_billing = new_billing or {}
    issues: list[BillingStatusIssue] = []

    for report_id in sorted(set(old_billing) | set(new_billing)):
        old_row = old_billing.get(report_id, {})
        new_row = new_billing.get(report_id, {})
        if not isinstance(old_row, dict):
            old_row = {}
        if not isinstance(new_row, dict):
            new_row = {}

        old_status = normalize_billing_status(old_row.get("status"))
        new_status = normalize_billing_status(new_row.get("status"))
        message = validate_billing_transition(old_status, new_status)
        if message:
            issues.append(BillingStatusIssue(
                report_id=str(report_id),
                old_status=old_status,
                new_status=new_status,
                message=message,
            ))

    return issues
