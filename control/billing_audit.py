# -*- coding: utf-8 -*-
"""
billing_audit.py - 請款變更稽核紀錄

這個模組只處理「old -> new」差異整理與 append-only JSONL 寫入。
OperationJournal 用來偵測中斷；billing_audit 則用來事後追查誰改了什麼。
"""

from __future__ import annotations

import getpass
import json
import os
import socket
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from billing_status import UNBILLED


BILLING_AUDIT_FILENAME = "billing_audit.jsonl"
BILLING_FIELDS = (
    "status",
    "billing_date",
    "weld_amount",
    "material_amount",
    "total",
    "remark",
)
AMOUNT_FIELDS = {"weld_amount", "material_amount", "total"}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_row(row: Any) -> dict[str, str]:
    if not isinstance(row, dict):
        row = {}
    return {field: _text(row.get(field)) for field in BILLING_FIELDS}


def _is_empty(row: dict[str, str]) -> bool:
    return (
        row.get("status", "") in ("", UNBILLED)
        and all(not row.get(field) for field in BILLING_FIELDS if field != "status")
    )


def _change_types(changes: dict[str, dict[str, str]]) -> list[str]:
    types: set[str] = set()
    if "status" in changes:
        types.add("status")
    if "billing_date" in changes:
        types.add("billing_date")
    if any(field in changes for field in AMOUNT_FIELDS):
        types.add("amount")
    if "remark" in changes:
        types.add("remark")
    return sorted(types)


def build_billing_change_events(
    old_billing: dict[str, dict[str, Any]] | None,
    new_billing: dict[str, dict[str, Any]] | None,
    *,
    operation_id: str | None = None,
    actor: str | None = None,
    host: str | None = None,
    at: str | None = None,
) -> list[dict[str, Any]]:
    """建立請款差異事件；完全空白的新舊列不產生事件。"""
    old_billing = old_billing or {}
    new_billing = new_billing or {}
    operation_id = operation_id or uuid.uuid4().hex
    actor = actor or getpass.getuser()
    host = host or socket.gethostname()
    at = at or _now_iso()

    events: list[dict[str, Any]] = []
    for report_id in sorted(set(old_billing) | set(new_billing)):
        old_row = _normalize_row(old_billing.get(report_id))
        new_row = _normalize_row(new_billing.get(report_id))
        if old_row == new_row:
            continue
        if _is_empty(old_row) and _is_empty(new_row):
            continue

        changes = {
            field: {"old": old_row[field], "new": new_row[field]}
            for field in BILLING_FIELDS
            if old_row[field] != new_row[field]
        }

        if _is_empty(old_row):
            action = "created"
        elif _is_empty(new_row):
            action = "cleared"
        else:
            action = "updated"

        events.append({
            "schema_version": 1,
            "event_id": uuid.uuid4().hex,
            "operation_id": operation_id,
            "at": at,
            "actor": actor,
            "host": host,
            "report_id": str(report_id),
            "action": action,
            "change_types": _change_types(changes),
            "changes": changes,
        })

    return events


def billing_audit_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / "records" / BILLING_AUDIT_FILENAME


def append_billing_audit(
    project_root: str | Path,
    events: list[dict[str, Any]],
    *,
    path: str | Path | None = None,
) -> tuple[Path, int]:
    """將請款稽核事件附加到 JSONL 檔案。"""
    target = Path(path).resolve() if path else billing_audit_path(project_root)
    if not events:
        return target, 0

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        for event in events:
            json.dump(event, f, ensure_ascii=False, sort_keys=True)
            f.write("\n")
            f.flush()
        os.fsync(f.fileno())

    return target, len(events)
