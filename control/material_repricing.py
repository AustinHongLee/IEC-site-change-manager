# -*- coding: utf-8 -*-
"""
material_repricing.py - 未定價材料重配價

補完材料價目表後，用這裡只更新仍未定價的材料明細。手動價與已請款鎖定
修改單不會被覆蓋。
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import record_manager
from billing_calculator import parse_amount
from billing_status import is_billing_locked
from material_audit import append_material_audit, build_material_reprice_event
from material_pricebook import (
    PRICE_SOURCE_MISSING,
    PRICE_SOURCE_MISSING_PRICE,
    apply_material_pricing,
    load_material_pricebook,
)
from operation_journal import OperationJournal


REPRICEABLE_PRICE_SOURCES = {"", PRICE_SOURCE_MISSING, PRICE_SOURCE_MISSING_PRICE}
REPRICEABLE_STATUSES = {"", PRICE_SOURCE_MISSING, PRICE_SOURCE_MISSING_PRICE}


def load_locked_report_ids(billing_path: str | None = None) -> set[str]:
    path = billing_path or record_manager.BILLING_JSON_PATH
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return set()
    billing = data.get("billing", {}) if isinstance(data, dict) else {}
    if not isinstance(billing, dict):
        return set()
    locked: set[str] = set()
    for report_id, row in billing.items():
        if not isinstance(row, dict):
            continue
        status = row.get("status") or row.get("請款狀態") or ""
        if is_billing_locked(status):
            locked.add(str(report_id))
    return locked


def is_reprice_candidate(material: dict[str, Any]) -> bool:
    if not str(material.get("零件類型", "")).strip():
        return False
    if str(material.get("單價來源", "")).strip() == "manual":
        return False
    if str(material.get("金額來源", "")).strip() == "manual":
        return False
    if parse_amount(material.get("單價")) is not None:
        return False
    source = str(material.get("單價來源", "")).strip()
    status = str(material.get("配價狀態", "")).strip()
    return source in REPRICEABLE_PRICE_SOURCES or status in REPRICEABLE_STATUSES


def build_reprice_plan(
    store: dict[str, Any],
    pricebook: dict[str, Any],
    *,
    locked_report_ids: set[str] | None = None,
) -> dict[str, Any]:
    updated_store = copy.deepcopy(store)
    operation_id = uuid.uuid4().hex
    changed_report_ids: set[str] = set()
    audit_events: list[dict[str, Any]] = []
    materials = updated_store.get("materials", [])
    if not isinstance(materials, list):
        materials = []
        updated_store["materials"] = materials
    locked_report_ids = locked_report_ids or set()
    summary = {
        "total_materials": len(materials),
        "candidates": 0,
        "updated": 0,
        "matched": 0,
        "missing_price": 0,
        "missing_pricebook": 0,
        "skipped_locked": 0,
        "skipped_manual": 0,
        "affected_reports": 0,
    }

    for idx, material in enumerate(materials):
        if not isinstance(material, dict):
            continue
        report_id = str(material.get("報告編號", "")).strip()
        if report_id in locked_report_ids:
            if is_reprice_candidate(material):
                summary["skipped_locked"] += 1
            continue
        if (
            str(material.get("單價來源", "")).strip() == "manual"
            or str(material.get("金額來源", "")).strip() == "manual"
        ):
            if parse_amount(material.get("單價")) is None:
                summary["skipped_manual"] += 1
            continue
        if not is_reprice_candidate(material):
            continue

        summary["candidates"] += 1
        priced = apply_material_pricing([material], pricebook)[0]
        status = str(priced.get("配價狀態", "")).strip()
        before = dict(material)
        material.update(priced)
        if material != before:
            summary["updated"] += 1
            if report_id and _material_financial_fields_changed(before, material):
                changed_report_ids.add(report_id)
            event = build_material_reprice_event(before, material, operation_id=operation_id)
            if event:
                audit_events.append(event)
        if status == "matched" and parse_amount(priced.get("單價")) is not None:
            summary["matched"] += 1
        elif status == PRICE_SOURCE_MISSING_PRICE:
            summary["missing_price"] += 1
        elif status == PRICE_SOURCE_MISSING:
            summary["missing_pricebook"] += 1

    _mark_records_need_rebuild(
        updated_store,
        changed_report_ids,
        reason="材料補價後金額變更",
    )
    summary["affected_reports"] = len(changed_report_ids)

    return {
        "store": updated_store,
        "summary": summary,
        "operation_id": operation_id,
        "affected_report_ids": sorted(changed_report_ids),
        "audit_events": audit_events,
    }


def build_project_reprice_plan(
    *,
    pricebook: dict[str, Any] | None = None,
    billing_path: str | None = None,
) -> dict[str, Any]:
    store = record_manager._load_store()
    pricebook = pricebook if pricebook is not None else load_material_pricebook()
    locked_report_ids = load_locked_report_ids(billing_path)
    return build_reprice_plan(store, pricebook, locked_report_ids=locked_report_ids)


def apply_project_reprice_plan(plan: dict[str, Any]) -> None:
    project_root = _project_root_from_records_path(record_manager.RECORDS_JSON_PATH)
    journal = OperationJournal(project_root, "material_reprice", {
        "operation_id": plan.get("operation_id", ""),
        "summary": plan.get("summary", {}),
        "affected_report_ids": plan.get("affected_report_ids", []),
    }).begin()
    try:
        journal.step("auto_backup_records", path=record_manager.RECORDS_JSON_PATH)
        record_manager.auto_backup(record_manager.RECORDS_JSON_PATH)
        journal.step("save_records_json", path=record_manager.RECORDS_JSON_PATH)
        record_manager._save_store(plan["store"])
        audit_events = plan.get("audit_events", [])
        journal.step("append_material_audit", count=len(audit_events))
        append_material_audit(project_root, audit_events)
        journal.complete()
    except Exception as exc:
        journal.fail(str(exc))
        raise


def format_reprice_summary(summary: dict[str, int]) -> str:
    return "\n".join([
        f"材料總筆數: {summary.get('total_materials', 0)}",
        f"待重配未定價: {summary.get('candidates', 0)}",
        f"可套用補價: {summary.get('matched', 0)}",
        f"受影響修改單: {summary.get('affected_reports', 0)}",
        f"仍未填單價: {summary.get('missing_price', 0)}",
        f"仍無價目: {summary.get('missing_pricebook', 0)}",
        f"已請款略過: {summary.get('skipped_locked', 0)}",
        f"手動價略過: {summary.get('skipped_manual', 0)}",
    ])


def _mark_records_need_rebuild(store: dict[str, Any], report_ids: set[str], *, reason: str) -> None:
    if not report_ids:
        return
    now = datetime.now().isoformat(timespec="seconds")
    for record in store.get("records", []) or []:
        if not isinstance(record, dict):
            continue
        report_id = str(record.get("報告編號", "")).strip()
        if report_id in report_ids:
            record["需重產"] = "1"
            record["需重產原因"] = reason
            record["需重產時間"] = now


def _material_financial_fields_changed(old: dict[str, Any], new: dict[str, Any]) -> bool:
    return (
        str(old.get("單價", "")).strip() != str(new.get("單價", "")).strip()
        or str(old.get("金額", "")).strip() != str(new.get("金額", "")).strip()
    )


def _project_root_from_records_path(path: str) -> Path:
    records_path = Path(path).resolve()
    if records_path.parent.name == "records":
        return records_path.parent.parent
    return records_path.parent
