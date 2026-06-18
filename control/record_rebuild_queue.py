# -*- coding: utf-8 -*-
"""
record_rebuild_queue.py - 需重產修改單清單

材料補價或其他資料異動可能讓已產出的 PDF/Excel 與 records 金額不同。
這裡集中整理「需重產」清單，供 UI 與 CLI/測試共用。
"""

from __future__ import annotations

import csv
import os
from typing import Any

from material_pricebook import unresolved_material_counts_by_report


REBUILD_QUEUE_HEADERS = [
    "報告編號",
    "日期",
    "Series NO",
    "資料夾名",
    "焊口清單",
    "變更類型",
    "說明",
    "需重產原因",
    "需重產時間",
    "待補價",
    "待建料",
]


def build_rebuild_queue(store: dict[str, Any]) -> list[dict[str, str]]:
    unresolved_counts = unresolved_material_counts_by_report(store.get("materials", []))
    rows: list[dict[str, str]] = []
    for record in store.get("records", []) or []:
        if not isinstance(record, dict):
            continue
        if str(record.get("需重產", "")).strip() != "1":
            continue
        report_id = str(record.get("報告編號", "")).strip()
        counts = unresolved_counts.get(report_id, {})
        rows.append({
            "報告編號": report_id,
            "日期": str(record.get("日期", "")).strip(),
            "Series NO": str(record.get("Series NO", "")).strip(),
            "資料夾名": str(record.get("資料夾名", "")).strip(),
            "焊口清單": str(record.get("焊口清單", "")).strip(),
            "變更類型": str(record.get("變更類型", "")).strip(),
            "說明": str(record.get("說明", "")).strip(),
            "需重產原因": str(record.get("需重產原因", "")).strip(),
            "需重產時間": str(record.get("需重產時間", "")).strip(),
            "待補價": str(int((counts or {}).get("missing_price", 0))),
            "待建料": str(int((counts or {}).get("missing_pricebook", 0))),
        })
    return rows


def format_rebuild_queue_summary(rows: list[dict[str, str]], *, max_items: int = 12) -> str:
    if not rows:
        return "目前沒有需重產的修改單。"
    lines = [f"需重產修改單：{len(rows)} 張", ""]
    for row in rows[:max_items]:
        label = row.get("報告編號", "") or row.get("資料夾名", "") or "未命名"
        reason = row.get("需重產原因", "") or "資料已變更"
        lines.append(f"- {label}：{reason}")
    if len(rows) > max_items:
        lines.append(f"...另有 {len(rows) - max_items} 張")
    return "\n".join(lines)


def export_rebuild_queue_csv(path: str, rows: list[dict[str, str]]) -> str:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REBUILD_QUEUE_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in REBUILD_QUEUE_HEADERS})
    return path
