# -*- coding: utf-8 -*-
"""
material_audit.py - 材料變更 append-only 稽核紀錄

記錄材料重配價等財務敏感變更。OperationJournal 用來偵測中斷；
material_audit 則用來事後查「哪張單、哪筆材料、由什麼值變成什麼值」。
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


MATERIAL_AUDIT_FILENAME = "material_audit.jsonl"
MATERIAL_AUDIT_FIELDS = (
    "零件類型",
    "尺寸",
    "SCH",
    "材質",
    "類別",
    "數量",
    "單位",
    "單價",
    "金額",
    "單價來源",
    "金額來源",
    "價目表ID",
    "價目來源",
    "價目生效日",
    "配價狀態",
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_material(row: Any) -> dict[str, str]:
    if not isinstance(row, dict):
        row = {}
    return {field: _text(row.get(field)) for field in MATERIAL_AUDIT_FIELDS}


def _material_key(row: dict[str, str]) -> dict[str, str]:
    return {
        "component": row.get("零件類型", ""),
        "size": row.get("尺寸", ""),
        "sch": row.get("SCH", ""),
        "material": row.get("材質", ""),
    }


def _change_types(changes: dict[str, dict[str, str]]) -> list[str]:
    types: set[str] = set()
    if any(field in changes for field in ("單價", "金額", "單價來源", "金額來源", "配價狀態")):
        types.add("pricing")
    if any(field in changes for field in ("價目表ID", "價目來源", "價目生效日")):
        types.add("pricebook")
    if any(field in changes for field in ("零件類型", "尺寸", "SCH", "材質", "單位", "類別", "數量")):
        types.add("material")
    return sorted(types)


def build_material_reprice_event(
    old_material: dict[str, Any],
    new_material: dict[str, Any],
    *,
    operation_id: str | None = None,
    actor: str | None = None,
    host: str | None = None,
    at: str | None = None,
) -> dict[str, Any] | None:
    old_row = _normalize_material(old_material)
    new_row = _normalize_material(new_material)
    changes = {
        field: {"old": old_row[field], "new": new_row[field]}
        for field in MATERIAL_AUDIT_FIELDS
        if old_row[field] != new_row[field]
    }
    if not changes:
        return None

    operation_id = operation_id or uuid.uuid4().hex
    actor = actor or getpass.getuser()
    host = host or socket.gethostname()
    at = at or _now_iso()
    report_id = _text(new_material.get("報告編號") or old_material.get("報告編號"))
    item_no = _text(new_material.get("項目") or old_material.get("項目"))

    return {
        "schema_version": 1,
        "event_id": uuid.uuid4().hex,
        "operation_id": operation_id,
        "at": at,
        "actor": actor,
        "host": host,
        "report_id": report_id,
        "item_no": item_no,
        "action": "repriced",
        "change_types": _change_types(changes),
        "material_key": _material_key(new_row),
        "changes": changes,
    }


def material_audit_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / "records" / MATERIAL_AUDIT_FILENAME


def append_material_audit(
    project_root: str | Path,
    events: list[dict[str, Any]],
    *,
    path: str | Path | None = None,
) -> tuple[Path, int]:
    target = Path(path).resolve() if path else material_audit_path(project_root)
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
