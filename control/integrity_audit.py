# -*- coding: utf-8 -*-
"""
integrity_audit.py - 專案資料一致性稽核

這裡檢查的是「資料之間有沒有對不起來」，不同於 project_guard
檢查啟動必要檔案是否存在。稽核只讀取資料，不自動修改。
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from billing_batch import batch_report_ids, validate_billing_batches
from project_guard import safe_load_json


@dataclass
class AuditIssue:
    severity: str
    code: str
    title: str
    message: str
    refs: list[str] = field(default_factory=list)


@dataclass
class IntegrityReport:
    root: str
    counts: dict[str, int] = field(default_factory=dict)
    issues: list[AuditIssue] = field(default_factory=list)

    def add_issue(
        self,
        severity: str,
        code: str,
        title: str,
        message: str,
        refs: list[str] | None = None,
    ) -> None:
        self.issues.append(AuditIssue(severity, code, title, message, refs or []))

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    def count_by_severity(self) -> dict[str, int]:
        counter = Counter(i.severity for i in self.issues)
        return {key: counter.get(key, 0) for key in ("error", "warning", "info")}


def _read_json_or_issue(report: IntegrityReport, path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        report.add_issue(
            "warning",
            f"{label}_missing",
            f"{path.name} 不存在",
            "稽核時找不到此資料檔。",
            [str(path)],
        )
        return {}
    data, error = safe_load_json(path)
    if error:
        report.add_issue(
            "error",
            f"{label}_invalid_json",
            f"{path.name} 無法讀取",
            f"JSON 損壞或格式錯誤：{error}",
            [str(path)],
        )
        return {}
    return data or {}


def _attachment_folders(attachments_root: Path) -> set[tuple[str, str]]:
    folders: set[tuple[str, str]] = set()
    if not attachments_root.is_dir():
        return folders
    for date_dir in sorted(attachments_root.iterdir()):
        if not date_dir.is_dir() or date_dir.name.startswith("_"):
            continue
        if not re.fullmatch(r"\d{8}", date_dir.name):
            continue
        for folder in sorted(date_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("_"):
                folders.add((date_dir.name, folder.name))
    return folders


def _extract_billing_refs(billing_store: dict[str, Any]) -> set[str]:
    refs: set[str] = set()

    billing = billing_store.get("billing")
    if isinstance(billing, dict):
        for key, value in billing.items():
            if isinstance(key, str) and key and key != "meta":
                refs.add(key)
            if isinstance(value, dict):
                rid = value.get("report_id") or value.get("報告編號")
                if rid:
                    refs.add(str(rid))
            elif isinstance(value, list):
                refs |= _extract_refs_from_list(value)
    elif isinstance(billing, list):
        refs |= _extract_refs_from_list(billing)

    refs |= _extract_refs_from_list(billing_store.get("billing_items", []))
    refs |= _extract_refs_from_list(billing_store.get("items", []))

    return {r for r in refs if r}


def _extract_refs_from_list(items: Any) -> set[str]:
    refs: set[str] = set()
    if not isinstance(items, list):
        return refs
    for item in items:
        if not isinstance(item, dict):
            continue
        rid = item.get("report_id") or item.get("報告編號") or item.get("record_id")
        if rid:
            refs.add(str(rid))
    return refs


def _extract_billing_batch_refs(batch_store: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    batches = batch_store.get("batches", [])
    if not isinstance(batches, list):
        return refs
    for batch in batches:
        if isinstance(batch, dict):
            refs.update(batch_report_ids(batch))
    return {r for r in refs if r}


def _has_before_after(folder_path: Path) -> tuple[bool, bool]:
    before = (folder_path / "before.jpg").exists() or any(folder_path.glob("before_*.jpg"))
    after = (folder_path / "after.jpg").exists() or any(folder_path.glob("after_*.jpg"))
    return before, after


def audit_integrity(project_root: str | Path) -> IntegrityReport:
    root = Path(project_root).resolve()
    report = IntegrityReport(root=str(root))

    records_store = _read_json_or_issue(report, root / "records" / "records.json", "records")
    billing_store = _read_json_or_issue(report, root / "records" / "billing.json", "billing")
    billing_batch_store = _read_json_or_issue(report, root / "records" / "billing_batches.json", "billing_batches")
    dwg_store = _read_json_or_issue(report, root / "records" / "dwg_map.json", "dwg_map")
    snapshot_store = {}
    snapshot_path = root / "records" / "weld_snapshot.json"
    if snapshot_path.exists():
        snapshot_store = _read_json_or_issue(report, snapshot_path, "weld_snapshot")

    records = records_store.get("records", [])
    details = records_store.get("details", [])
    materials = records_store.get("materials", [])
    if not isinstance(records, list):
        records = []
    if not isinstance(details, list):
        details = []
    if not isinstance(materials, list):
        materials = []

    attachments = _attachment_folders(root / "attachments")
    record_keys = {
        (str(r.get("日期", "")), str(r.get("資料夾名", "")))
        for r in records
        if r.get("日期") and r.get("資料夾名")
    }
    record_ids = {str(r.get("報告編號", "")) for r in records if r.get("報告編號")}

    report.counts.update({
        "records": len(records),
        "details": len(details),
        "materials": len(materials),
        "attachment_folders": len(attachments),
        "billing_refs": len(_extract_billing_refs(billing_store)),
        "billing_batch_refs": len(_extract_billing_batch_refs(billing_batch_store)),
        "dwg_entries": len(dwg_store.get("mapping", dwg_store.get("map", {})) or {}),
        "snapshot_folders": len(snapshot_store.get("folders", {}) or {}),
        "snapshot_welds": len(snapshot_store.get("weld_index", {}) or {}),
    })

    for issue in validate_billing_batches(billing_batch_store):
        severity = "error" if issue.code == "duplicate_active_report" else "warning"
        report.add_issue(
            severity,
            f"billing_batch_{issue.code}",
            "請款批次資料異常",
            issue.message,
            [issue.report_id or issue.batch_id],
        )

    # 1. records -> attachments
    missing_attachment_refs = []
    for rec in records:
        key = (str(rec.get("日期", "")), str(rec.get("資料夾名", "")))
        if key[0] and key[1] and key not in attachments:
            rid = str(rec.get("報告編號", ""))
            missing_attachment_refs.append(f"{rid} | {key[0]}/{key[1]}")
    if missing_attachment_refs:
        report.add_issue(
            "error",
            "records_missing_attachments",
            "有 records 指向不存在的附件資料夾",
            f"{len(missing_attachment_refs)} 筆紀錄找不到對應 attachments 資料夾。",
            missing_attachment_refs,
        )

    # 2. attachments -> records
    orphan_attachments = sorted(attachments - record_keys)
    if orphan_attachments:
        report.add_issue(
            "warning",
            "attachments_without_records",
            "有附件資料夾尚未產出 records",
            f"{len(orphan_attachments)} 個 attachments 子資料夾尚未寫入 records.json。",
            [f"{d}/{f}" for d, f in orphan_attachments],
        )

    # 3. details -> records
    orphan_details = []
    for detail in details:
        rid = detail.get("紀錄編號") or detail.get("報告編號")
        if rid and str(rid) not in record_ids:
            orphan_details.append(str(rid))
    if orphan_details:
        uniq = sorted(set(orphan_details))
        report.add_issue(
            "error",
            "details_without_records",
            "有焊口明細指向不存在的修改單",
            f"{len(uniq)} 個紀錄編號沒有對應 record。",
            uniq,
        )

    # 4. duplicate report IDs
    rid_counts = Counter(str(r.get("報告編號", "")) for r in records if r.get("報告編號"))
    dup_rids = {rid: count for rid, count in rid_counts.items() if count > 1}
    if dup_rids:
        report.add_issue(
            "error",
            "duplicate_report_ids",
            "報告編號重複",
            f"{len(dup_rids)} 個報告編號重複。",
            [f"{rid}: {count}" for rid, count in sorted(dup_rids.items())],
        )

    # 5. duplicate date/folder keys
    key_counts = Counter(
        (str(r.get("日期", "")), str(r.get("資料夾名", "")))
        for r in records
        if r.get("日期") and r.get("資料夾名")
    )
    dup_keys = {key: count for key, count in key_counts.items() if count > 1}
    if dup_keys:
        report.add_issue(
            "error",
            "duplicate_record_folder_keys",
            "同一日期/資料夾重複",
            f"{len(dup_keys)} 組 (日期, 資料夾) 重複。",
            [f"{d}/{folder}: {count}" for (d, folder), count in sorted(dup_keys.items())],
        )

    # 6. image flags vs files
    image_mismatches = []
    for rec in records:
        date = str(rec.get("日期", ""))
        folder = str(rec.get("資料夾名", ""))
        if not date or not folder:
            continue
        folder_path = root / "attachments" / date / folder
        if not folder_path.is_dir():
            continue
        rec_before = rec.get("before.jpg", "") == "有"
        rec_after = rec.get("after.jpg", "") == "有"
        real_before, real_after = _has_before_after(folder_path)
        parts = []
        if rec_before != real_before:
            parts.append(f"before record={rec_before} real={real_before}")
        if rec_after != real_after:
            parts.append(f"after record={rec_after} real={real_after}")
        if parts:
            rid = str(rec.get("報告編號", ""))
            image_mismatches.append(f"{rid} | {date}/{folder}: {'; '.join(parts)}")
    if image_mismatches:
        report.add_issue(
            "warning",
            "image_flag_mismatch",
            "照片欄位與實際檔案不一致",
            f"{len(image_mismatches)} 筆紀錄的 before/after 欄位與檔案不一致。",
            image_mismatches,
        )

    # 7. PDF outputs
    missing_pdfs = []
    for rec in records:
        rid = str(rec.get("報告編號", ""))
        date = str(rec.get("日期", ""))
        if not rid:
            continue
        candidates = [
            root / "pdf" / f"{rid}.pdf",
            root / "pdf" / date / f"{rid}.pdf",
        ]
        if not any(path.exists() for path in candidates):
            missing_pdfs.append(rid)
    if missing_pdfs:
        report.add_issue(
            "warning",
            "records_missing_pdf",
            "有 records 找不到 PDF 產出檔",
            f"{len(missing_pdfs)} 筆紀錄找不到對應 PDF。",
            missing_pdfs,
        )

    # 8. _ERROR markers
    error_markers = []
    for date, folder in sorted(attachments):
        marker = root / "attachments" / date / folder / "_ERROR.txt"
        if marker.exists():
            error_markers.append(f"{date}/{folder}")
    if error_markers:
        report.add_issue(
            "warning",
            "error_markers_present",
            "仍有失敗標記",
            f"{len(error_markers)} 個附件資料夾仍有 _ERROR.txt。",
            error_markers,
        )

    # 9. weld snapshot staleness
    snapshot_folders = set((snapshot_store.get("folders", {}) or {}).keys())
    real_folders = {f"{d}/{folder}" for d, folder in attachments}
    missing_in_snapshot = sorted(real_folders - snapshot_folders)
    stale_in_snapshot = sorted(snapshot_folders - real_folders)
    if snapshot_store and (missing_in_snapshot or stale_in_snapshot):
        refs = []
        refs += [f"missing_in_snapshot: {x}" for x in missing_in_snapshot]
        refs += [f"stale_in_snapshot: {x}" for x in stale_in_snapshot]
        report.add_issue(
            "warning",
            "weld_snapshot_stale",
            "焊口快照與 attachments 不一致",
            "weld_snapshot.json 需要重建。",
            refs,
        )

    # 10. billing refs
    billing_refs = _extract_billing_refs(billing_store)
    orphan_billing = sorted(billing_refs - record_ids)
    if orphan_billing:
        report.add_issue(
            "error",
            "billing_refs_missing_records",
            "請款資料指向不存在的修改單",
            f"{len(orphan_billing)} 筆請款參照沒有對應 record。",
            orphan_billing,
        )

    return report


def format_integrity_report(report: IntegrityReport, *, max_refs: int = 12) -> str:
    lines = [f"資料一致性稽核: {report.root}"]
    counts = report.counts
    lines.append(
        "資料量: "
        f"records={counts.get('records', 0)}, "
        f"details={counts.get('details', 0)}, "
        f"materials={counts.get('materials', 0)}, "
        f"attachments={counts.get('attachment_folders', 0)}, "
        f"billing_refs={counts.get('billing_refs', 0)}"
    )
    severity = report.count_by_severity()
    lines.append(
        "問題摘要: "
        f"error={severity['error']}, "
        f"warning={severity['warning']}, "
        f"info={severity['info']}"
    )

    if not report.issues:
        lines.append("結果: 資料一致。")
        return "\n".join(lines)

    lines.append("")
    lines.append("問題列表:")
    for issue in report.issues:
        lines.append(f"- [{issue.severity.upper()}] {issue.title}: {issue.message}")
        for ref in issue.refs[:max_refs]:
            lines.append(f"  - {ref}")
        if len(issue.refs) > max_refs:
            lines.append(f"  - ... 還有 {len(issue.refs) - max_refs} 筆")
    return "\n".join(lines)
