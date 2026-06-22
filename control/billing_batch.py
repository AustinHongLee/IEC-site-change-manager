# -*- coding: utf-8 -*-
"""
billing_batch.py - 請款批次資料層

v1 先建立最小資料契約：
- records/billing_batches.json
- 一張修改單不可同時存在於兩個活躍請款批次
- 批次狀態集中驗證，之後 UI 可直接接這層
"""

from __future__ import annotations

import copy
import getpass
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from billing_calculator import (
    BILLING_CURRENCY,
    BILLING_ROUNDING_RULE,
    BILLING_TAX_MODE,
    tax_rate_to_text,
)
from utils import atomic_write_json
from resources import project_path


BILLING_BATCHES_JSON_PATH = project_path("records", "billing_batches.json")
BILLING_BATCH_VERSION = "1.0"

BATCH_DRAFT = "草稿"
BATCH_STATUS_OPTIONS = (
    BATCH_DRAFT,
    "請款中",
    "已請款",
    "部分付款",
    "已付款",
    "補件中",
    "退回",
    "已結案",
    "作廢",
)
BATCH_STATUS_SET = set(BATCH_STATUS_OPTIONS)
CLOSED_BATCH_STATUSES = {"已結案", "作廢"}
ACTIVE_BATCH_STATUSES = BATCH_STATUS_SET - CLOSED_BATCH_STATUSES

BATCH_ALLOWED_TRANSITIONS = {
    BATCH_DRAFT: {BATCH_DRAFT, "請款中", "作廢"},
    "請款中": {"請款中", "已請款", "補件中", "退回", "作廢"},
    "補件中": {"補件中", "請款中", "退回", "作廢"},
    "退回": {"退回", "補件中", "請款中", "作廢"},
    "已請款": {"已請款", "部分付款", "已付款", "補件中", "退回", "已結案"},
    "部分付款": {"部分付款", "已付款", "補件中", "已結案"},
    "已付款": {"已付款", "已結案"},
    "已結案": {"已結案"},
    "作廢": {"作廢"},
}


DEFAULT_BILLING_BATCHES: dict[str, Any] = {
    "batches": [],
    "meta": {
        "version": BILLING_BATCH_VERSION,
        "currency": BILLING_CURRENCY,
        "tax_mode": BILLING_TAX_MODE,
        "tax_rate": tax_rate_to_text(),
        "rounding_rule": BILLING_ROUNDING_RULE,
    },
}


@dataclass(frozen=True)
class BillingBatchIssue:
    code: str
    message: str
    batch_id: str = ""
    report_id: str = ""


class BillingBatchError(ValueError):
    def __init__(self, issues: list[BillingBatchIssue]):
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_billing_batches() -> dict[str, Any]:
    data = copy.deepcopy(DEFAULT_BILLING_BATCHES)
    data["meta"]["created_at"] = now_iso()
    data["meta"]["last_modified"] = now_iso()
    return data


def load_billing_batches(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path or BILLING_BATCHES_JSON_PATH)
    if not path.exists():
        return default_billing_batches()

    import json

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return default_billing_batches()
    return normalize_billing_batches(data)


def save_billing_batches(data: dict[str, Any], path: str | Path | None = None) -> None:
    path = Path(path or BILLING_BATCHES_JSON_PATH)
    normalized = normalize_billing_batches(data)
    issues = validate_billing_batches(normalized)
    if issues:
        raise BillingBatchError(issues)
    normalized.setdefault("meta", {})["last_modified"] = now_iso()
    atomic_write_json(str(path), normalized)


def create_billing_batch(
    report_ids: list[str],
    *,
    path: str | Path | None = None,
    batch_id: str | None = None,
    status: str = BATCH_DRAFT,
    client: str = "",
    period: str = "",
    actor: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    data = load_billing_batches(path)
    batch = build_billing_batch(
        report_ids,
        batch_id=batch_id,
        status=status,
        client=client,
        period=period,
        actor=actor,
        at=at,
    )
    data["batches"].append(batch)
    save_billing_batches(data, path)
    return batch


def build_billing_batch(
    report_ids: list[str],
    *,
    batch_id: str | None = None,
    status: str = BATCH_DRAFT,
    client: str = "",
    period: str = "",
    actor: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    at = at or now_iso()
    actor = actor or getpass.getuser()
    report_ids = _unique_report_ids(report_ids)
    if not report_ids:
        raise BillingBatchError([
            BillingBatchIssue("empty_batch", "請款批次至少需要一張修改單")
        ])

    batch = {
        "batch_id": batch_id or _make_batch_id(at),
        "status": normalize_batch_status(status),
        "client": str(client or "").strip(),
        "period": str(period or "").strip(),
        "created_at": at,
        "created_by": actor,
        "updated_at": at,
        "updated_by": actor,
        "host": socket.gethostname(),
        "items": [
            {"report_id": report_id, "status": "included", "added_at": at}
            for report_id in report_ids
        ],
    }
    issues = validate_billing_batches({"batches": [batch]})
    if issues:
        raise BillingBatchError(issues)
    return batch


def update_billing_batch_status(
    data: dict[str, Any],
    batch_id: str,
    new_status: str,
    *,
    actor: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_billing_batches(data)
    target = None
    for batch in normalized.get("batches", []):
        if str(batch.get("batch_id", "")) == str(batch_id):
            target = batch
            break
    if target is None:
        raise BillingBatchError([
            BillingBatchIssue("batch_not_found", f"找不到請款批次：{batch_id}", str(batch_id))
        ])

    old_status = normalize_batch_status(target.get("status"))
    new_status = normalize_batch_status(new_status)
    issue = validate_batch_transition(old_status, new_status)
    if issue:
        raise BillingBatchError([BillingBatchIssue(
            "invalid_batch_transition",
            issue,
            str(batch_id),
        )])

    target["status"] = new_status
    target["updated_at"] = at or now_iso()
    target["updated_by"] = actor or getpass.getuser()
    return normalized


def normalize_billing_batches(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    normalized = copy.deepcopy(DEFAULT_BILLING_BATCHES)
    normalized.update({k: v for k, v in data.items() if k != "batches"})
    meta = normalized.setdefault("meta", {})
    meta["version"] = BILLING_BATCH_VERSION
    meta.setdefault("currency", BILLING_CURRENCY)
    meta.setdefault("tax_mode", BILLING_TAX_MODE)
    meta.setdefault("tax_rate", tax_rate_to_text())
    meta.setdefault("rounding_rule", BILLING_ROUNDING_RULE)

    batches = data.get("batches", [])
    if not isinstance(batches, list):
        batches = []
    normalized["batches"] = [
        _normalize_batch(batch)
        for batch in batches
        if isinstance(batch, dict)
    ]
    return normalized


def validate_billing_batches(data: dict[str, Any] | None) -> list[BillingBatchIssue]:
    normalized = normalize_billing_batches(data)
    issues: list[BillingBatchIssue] = []
    seen_batch_ids: set[str] = set()
    active_owner: dict[str, str] = {}

    for idx, batch in enumerate(normalized.get("batches", []), start=1):
        batch_id = str(batch.get("batch_id", "")).strip()
        status = normalize_batch_status(batch.get("status"))
        if not batch_id:
            issues.append(BillingBatchIssue(
                "missing_batch_id",
                f"第 {idx} 個請款批次缺少 batch_id",
            ))
        elif batch_id in seen_batch_ids:
            issues.append(BillingBatchIssue(
                "duplicate_batch_id",
                f"請款批次 ID 重複：{batch_id}",
                batch_id,
            ))
        seen_batch_ids.add(batch_id)

        if status not in BATCH_STATUS_SET:
            issues.append(BillingBatchIssue(
                "invalid_batch_status",
                f"請款批次狀態「{status}」不是系統允許的狀態",
                batch_id,
            ))

        report_ids = batch_report_ids(batch)
        if not report_ids:
            issues.append(BillingBatchIssue(
                "empty_batch",
                f"請款批次 {batch_id or idx} 沒有任何修改單",
                batch_id,
            ))

        if is_active_batch_status(status):
            for report_id in report_ids:
                owner = active_owner.get(report_id)
                if owner and owner != batch_id:
                    issues.append(BillingBatchIssue(
                        "duplicate_active_report",
                        f"修改單 {report_id} 已存在於活躍請款批次 {owner}，不可同時加入 {batch_id}",
                        batch_id,
                        report_id,
                    ))
                else:
                    active_owner[report_id] = batch_id

    return issues


def active_batch_index(data: dict[str, Any] | None) -> dict[str, str]:
    normalized = normalize_billing_batches(data)
    index: dict[str, str] = {}
    for batch in normalized.get("batches", []):
        if not is_active_batch_status(batch.get("status")):
            continue
        batch_id = str(batch.get("batch_id", "")).strip()
        for report_id in batch_report_ids(batch):
            index.setdefault(report_id, batch_id)
    return index


def batch_report_ids(batch: dict[str, Any]) -> list[str]:
    items = batch.get("items")
    if isinstance(items, list):
        return _unique_report_ids(
            str(item.get("report_id", "")).strip()
            for item in items
            if isinstance(item, dict)
        )
    return _unique_report_ids(batch.get("report_ids", []))


def normalize_batch_status(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text or BATCH_DRAFT


def is_active_batch_status(value: Any) -> bool:
    return normalize_batch_status(value) in ACTIVE_BATCH_STATUSES


def validate_batch_transition(old_value: Any, new_value: Any) -> str | None:
    old_status = normalize_batch_status(old_value)
    new_status = normalize_batch_status(new_value)
    if new_status not in BATCH_STATUS_SET:
        return f"請款批次狀態「{new_status}」不是系統允許的狀態"
    if old_status not in BATCH_STATUS_SET:
        return None
    if new_status not in BATCH_ALLOWED_TRANSITIONS.get(old_status, {old_status}):
        return f"請款批次狀態不可由「{old_status}」直接改為「{new_status}」"
    return None


def _normalize_batch(batch: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(batch)
    normalized["batch_id"] = str(normalized.get("batch_id", "")).strip()
    normalized["status"] = normalize_batch_status(normalized.get("status"))
    normalized["client"] = str(normalized.get("client", "")).strip()
    normalized["period"] = str(normalized.get("period", "")).strip()
    normalized.setdefault("created_at", "")
    normalized.setdefault("created_by", "")
    normalized.setdefault("updated_at", normalized.get("created_at", ""))
    normalized.setdefault("updated_by", normalized.get("created_by", ""))
    report_ids = batch_report_ids(normalized)
    existing_items = normalized.get("items") if isinstance(normalized.get("items"), list) else []
    existing_by_id = {
        str(item.get("report_id", "")).strip(): item
        for item in existing_items
        if isinstance(item, dict) and str(item.get("report_id", "")).strip()
    }
    normalized["items"] = []
    for report_id in report_ids:
        item = dict(existing_by_id.get(report_id, {}))
        item["report_id"] = report_id
        item.setdefault("status", "included")
        item.setdefault("added_at", normalized.get("created_at", ""))
        normalized["items"].append(item)
    normalized.pop("report_ids", None)
    return normalized


def _unique_report_ids(values: Any) -> list[str]:
    seen: set[str] = set()
    report_ids: list[str] = []
    if isinstance(values, str):
        values = [values]
    for value in values or []:
        report_id = str(value).strip()
        if not report_id or report_id in seen:
            continue
        seen.add(report_id)
        report_ids.append(report_id)
    return report_ids


def _make_batch_id(at: str) -> str:
    stamp = at.replace("-", "").replace(":", "").replace("T", "-")[:15]
    return f"BILL-{stamp}-{uuid.uuid4().hex[:8]}"
