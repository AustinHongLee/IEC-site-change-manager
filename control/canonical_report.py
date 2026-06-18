# -*- coding: utf-8 -*-
"""
canonical_report.py - 現場資料核心模型收斂器

把 records.json 與 attachments/ 內的現場資料整理成穩定的
CanonicalReport / CanonicalReportSet。這層不做 Excel/PDF 輸出，也不依賴
Excel COM；所有 renderer 之後都應該吃這份資料模型。
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from canonical_fields import list_field_paths
import record_manager
from config import ATTACHMENTS_ROOT, BASE_DIR, use_dual_images
from parsers import build_auto_description, parse_folder, parse_materials_txt, weld_code_list
from utils import compute_fingerprint, find_attachment_pdf, scan_date_folders, scan_subfolders


CANONICAL_SCHEMA_VERSION = "report.v1"


def collect_canonical_report_set(
    *,
    project_root: str | Path | None = None,
    attachments_root: str | Path | None = None,
    store: dict[str, Any] | None = None,
    include_report_keys: Iterable[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    project_root = Path(project_root or BASE_DIR).resolve()
    attachments_root = Path(attachments_root or project_root / "attachments").resolve()
    if str(attachments_root) == str(Path(BASE_DIR).resolve() / "attachments"):
        attachments_root = Path(ATTACHMENTS_ROOT).resolve()
    store = store if store is not None else record_manager._load_store()

    record_by_folder = _index_records_by_folder(store)
    details_by_report = _group_by_report(store.get("details", []), "紀錄編號", "報告編號")
    materials_by_report = _group_by_report(store.get("materials", []), "報告編號")

    if include_report_keys is None:
        report_keys: set[tuple[str, str]] = set(record_by_folder)
        for date_dir in scan_date_folders(str(attachments_root)):
            date_path = attachments_root / date_dir
            for folder in scan_subfolders(str(date_path)):
                report_keys.add((date_dir, folder))
    else:
        report_keys = _normalize_report_keys(include_report_keys)

    reports = [
        _collect_report(
            date_str=date_str,
            folder_name=folder_name,
            attachments_root=attachments_root,
            record=record_by_folder.get((date_str, folder_name)),
            details_by_report=details_by_report,
            materials_by_report=materials_by_report,
        )
        for date_str, folder_name in sorted(report_keys)
    ]

    return {
        "schema_version": "report_set.v1",
        "project": {
            "root": str(project_root),
            "attachments_root": str(attachments_root),
            "collected_at": datetime.now().isoformat(timespec="seconds"),
        },
        "reports": reports,
        "aggregates": _build_report_set_aggregates(reports),
        "issues": _build_report_set_issues(reports),
        "field_paths": list_field_paths(),
    }


def _collect_report(
    *,
    date_str: str,
    folder_name: str,
    attachments_root: Path,
    record: dict[str, Any] | None,
    details_by_report: dict[str, list[dict[str, Any]]],
    materials_by_report: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    folder_path = attachments_root / date_str / folder_name
    folder_info = None
    parse_error = ""
    if folder_path.is_dir():
        try:
            folder_info = parse_folder(str(folder_path))
        except Exception as exc:
            parse_error = str(exc)

    report_id = _text(record, "報告編號")
    series = _text(record, "Series NO") or (folder_info.series_no if folder_info else _series_from_folder(folder_name))
    note_raw = folder_info.note_text if folder_info else ""
    materials_text = folder_info.materials_text if folder_info else _text(record, "材料附加")
    tokens = folder_info.tokens if folder_info else []
    status = _report_status(record, folder_path)

    description = _text(record, "說明")
    if not description and folder_info:
        description = build_auto_description(tokens, note_raw)

    weld_rows = _weld_rows_from_details(details_by_report.get(report_id, [])) if report_id else []
    if not weld_rows:
        weld_rows = _weld_rows_from_tokens(tokens)

    material_rows = _material_rows_from_records(materials_by_report.get(report_id, [])) if report_id else []
    if not material_rows and folder_path.is_dir():
        material_rows = _material_rows_from_parsed(parse_materials_txt(str(folder_path)))

    photo_data = _collect_photos(folder_path, folder_info.mode if folder_info else "", len(tokens))
    attachment_pdf = _collect_attachment_pdf(folder_path, series)
    fingerprint = _text(record, "內容指紋") or _compute_folder_fingerprint(
        date_str,
        folder_name,
        series,
        tokens,
        note_raw,
        materials_text,
        folder_path,
        folder_info.mode if folder_info else "",
    )
    completeness = _build_completeness(
        weld_rows=weld_rows,
        material_rows=material_rows,
        photos=photo_data,
        note_raw=note_raw,
        status=status,
        parse_error=parse_error,
    )

    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "report": {
            "report_id": report_id,
            "date": _date_text(date_str),
            "date_raw": date_str,
            "series": series,
            "dwg_no": _text(record, "DWG NO"),
            "line_number": _text(record, "LINE NUMBER"),
            "change_type": _text(record, "變更類型") or _infer_change_type(tokens),
            "description": description,
            "folder": folder_name,
            "folder_path": str(folder_path),
            "status": status,
            "fingerprint": fingerprint,
        },
        "welds": _build_welds(weld_rows),
        "materials": _build_materials(material_rows),
        "photos": photo_data,
        "attachment_pdf": attachment_pdf,
        "note": {
            "raw": note_raw,
            "is_placeholder": _is_placeholder_note(note_raw),
        },
        "completeness": completeness,
        "provenance": {
            "source_files": _source_files(folder_path),
            "parse_error": parse_error,
            "collected_at": datetime.now().isoformat(timespec="seconds"),
        },
    }


def _normalize_report_keys(keys: Iterable[tuple[str, str]]) -> set[tuple[str, str]]:
    normalized: set[tuple[str, str]] = set()
    for item in keys or []:
        try:
            date_str, folder_name = item
        except (TypeError, ValueError):
            continue
        date_str = str(date_str or "").strip()
        folder_name = str(folder_name or "").strip()
        if date_str and folder_name:
            normalized.add((date_str, folder_name))
    return normalized


def _index_records_by_folder(store: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for record in store.get("records", []) or []:
        if not isinstance(record, dict):
            continue
        date_str = _text(record, "日期")
        folder = _text(record, "資料夾名")
        if date_str and folder:
            indexed[(date_str, folder)] = record
    return indexed


def _group_by_report(rows: list[dict[str, Any]], *keys: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        report_id = ""
        for key in keys:
            report_id = _text(row, key)
            if report_id:
                break
        if report_id:
            grouped[report_id].append(row)
    return grouped


def _weld_rows_from_tokens(tokens) -> list[dict[str, Any]]:
    rows = []
    for token in tokens or []:
        rows.append({
            "weld_no": str(token.weld_no or ""),
            "mark": str(token.tag or ""),
            "size": token.size if token.size is not None else "",
            "material": "",
            "thickness": "",
            "code": token.code,
            "is_cut": bool(token.is_cut),
        })
    return rows


def _weld_rows_from_details(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for detail in details or []:
        code = _text(detail, "焊口編號")
        base = _split_weld_code(code)
        rows.append({
            "weld_no": base["weld_no"],
            "mark": base["mark"],
            "size": _number_or_text(detail.get("焊口尺寸")),
            "material": _text(detail, "材質"),
            "thickness": _text(detail, "厚度"),
            "code": code,
            "is_cut": "r" in code.lower(),
        })
    return rows


def _material_rows_from_parsed(materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_material_row(item) for item in materials or []]


def _material_rows_from_records(materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_material_row(item) for item in materials or []]


def _material_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "component": _text(item, "零件類型"),
        "size": _text(item, "尺寸"),
        "sch": _text(item, "SCH"),
        "material": _text(item, "材質"),
        "qty": _number_or_text(item.get("數量")),
        "unit": _text(item, "單位"),
        "category": _text(item, "類別") or "材料",
        "remark": _text(item, "備註"),
        "price": _text(item, "單價"),
        "amount": _text(item, "金額"),
        "pricing_status": _text(item, "配價狀態"),
    }


def _build_welds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_size: dict[str, int] = defaultdict(int)
    total_size = 0.0
    for row in rows:
        size = row.get("size")
        if size != "":
            by_size[str(size)] += 1
            try:
                total_size += float(size)
            except (TypeError, ValueError):
                pass
    codes = [str(row.get("code", "")).strip() for row in rows if str(row.get("code", "")).strip()]
    return {
        "rows": rows,
        "count": len(rows),
        "total_size": total_size,
        "summary": "、".join(codes) + (f"（共{len(rows)}口）" if rows else ""),
        "by_size": [{"size": size, "count": count} for size, count in sorted(by_size.items())],
    }


def _build_materials(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_component: dict[str, float] = defaultdict(float)
    for row in rows:
        component = str(row.get("component", "")).strip() or "未分類"
        try:
            qty = float(row.get("qty") or 0)
        except (TypeError, ValueError):
            qty = 0.0
        by_component[component] += qty
    parts = []
    for component, qty in sorted(by_component.items()):
        qty_text = str(int(qty)) if qty == int(qty) else str(qty)
        parts.append(f"{component}×{qty_text}")
    return {
        "rows": rows,
        "count": len(rows),
        "summary": "、".join(parts),
        "by_component": [
            {"component": component, "qty": qty}
            for component, qty in sorted(by_component.items())
        ],
    }


def _collect_photos(folder_path: Path, mode: str, token_count: int) -> dict[str, Any]:
    before = _photo_rows(folder_path, "before")
    after = _photo_rows(folder_path, "after")
    return {
        "before": before,
        "after": after,
        "mode": "dual" if use_dual_images(mode, token_count) else "single",
        "has_before": bool(before),
        "has_after": bool(after),
    }


def _photo_rows(folder_path: Path, prefix: str) -> list[dict[str, Any]]:
    if not folder_path.is_dir():
        return []
    paths = []
    for path in folder_path.iterdir():
        if not path.is_file():
            continue
        name = path.name.lower()
        if not name.startswith(prefix):
            continue
        if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp"):
            continue
        paths.append(path)
    return [_photo_info(path) for path in sorted(paths, key=lambda p: _photo_sort_key(p.name))]


def _photo_info(path: Path) -> dict[str, Any]:
    width = ""
    height = ""
    try:
        from PIL import Image
        with Image.open(path) as image:
            width, height = image.size
    except Exception:
        pass
    return {
        "path": str(path),
        "name": path.name,
        "exists": path.exists(),
        "w": width,
        "h": height,
    }


def _collect_attachment_pdf(folder_path: Path, series: str) -> dict[str, Any]:
    path = find_attachment_pdf(str(folder_path), series) if folder_path.is_dir() else None
    if not path:
        return {"path": "", "name": "", "exists": False, "pages": ""}
    return {
        "path": path,
        "name": os.path.basename(path),
        "exists": os.path.exists(path),
        "pages": _pdf_pages(path),
    }


def _pdf_pages(path: str) -> int | str:
    try:
        from pypdf import PdfReader
        return len(PdfReader(path).pages)
    except Exception:
        return ""


def _compute_folder_fingerprint(
    date_str: str,
    folder_name: str,
    series: str,
    tokens,
    note_raw: str,
    materials_text: str,
    folder_path: Path,
    mode: str,
) -> str:
    if not folder_path.is_dir():
        return ""
    try:
        return compute_fingerprint(
            date_str,
            folder_name,
            series,
            [token.raw for token in tokens or []],
            note_raw,
            materials_text,
            str(folder_path),
            is_group=(mode == "group"),
            use_dual_images=use_dual_images(mode, len(tokens or [])),
        )
    except Exception:
        return ""


def _build_completeness(
    *,
    weld_rows: list[dict[str, Any]],
    material_rows: list[dict[str, Any]],
    photos: dict[str, Any],
    note_raw: str,
    status: str,
    parse_error: str,
) -> dict[str, Any]:
    missing: list[str] = []
    flags = {
        "note_is_placeholder": _is_placeholder_note(note_raw),
        "no_material": not bool(material_rows),
        "no_welds": not bool(weld_rows),
        "parse_error": bool(parse_error),
        "unproduced": status == "unproduced",
        "needs_rebuild": status == "needs_rebuild",
    }
    if not weld_rows and not material_rows:
        missing.append("weld_or_material")
    if not photos.get("has_before"):
        missing.append("before_photo")
    if not photos.get("has_after"):
        missing.append("after_photo")
    if flags["note_is_placeholder"]:
        missing.append("note")
    if parse_error:
        missing.append("parse_error")
    level = "complete" if not missing else "incomplete"
    if not weld_rows and not material_rows and not photos.get("has_before") and not photos.get("has_after"):
        level = "empty"
    return {
        "level": level,
        "missing": missing,
        "flags": flags,
    }


def _build_report_set_aggregates(reports: list[dict[str, Any]]) -> dict[str, Any]:
    completeness_counts: dict[str, int] = defaultdict(int)
    status_counts: dict[str, int] = defaultdict(int)
    material_qty_by_key: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    weld_count_by_size: dict[str, int] = defaultdict(int)
    before_count = 0
    after_count = 0
    for report in reports:
        completeness_counts[report["completeness"]["level"]] += 1
        status_counts[report["report"]["status"]] += 1
        before_count += len(report["photos"]["before"])
        after_count += len(report["photos"]["after"])
        for weld in report["welds"]["rows"]:
            size = str(weld.get("size", "")).strip()
            if size:
                weld_count_by_size[size] += 1
        for material in report["materials"]["rows"]:
            key = (
                str(material.get("component", "")).strip(),
                str(material.get("size", "")).strip(),
                str(material.get("sch", "")).strip(),
                str(material.get("material", "")).strip(),
                str(material.get("unit", "")).strip(),
            )
            try:
                qty = float(material.get("qty") or 0)
            except (TypeError, ValueError):
                qty = 0.0
            material_qty_by_key[key] += qty
    return {
        "report_count": len(reports),
        "weld_count": sum(report["welds"]["count"] for report in reports),
        "material_row_count": sum(report["materials"]["count"] for report in reports),
        "photo_count": before_count + after_count,
        "before_photo_count": before_count,
        "after_photo_count": after_count,
        "completeness_counts": dict(completeness_counts),
        "status_counts": dict(status_counts),
        "weld_count_by_size": [
            {"size": size, "count": count}
            for size, count in sorted(weld_count_by_size.items())
        ],
        "material_qty_by_key": [
            {
                "component": key[0],
                "size": key[1],
                "sch": key[2],
                "material": key[3],
                "unit": key[4],
                "qty": qty,
            }
            for key, qty in sorted(material_qty_by_key.items())
        ],
    }


def _build_report_set_issues(reports: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for report in reports:
        report_info = report["report"]
        report_id = report_info.get("report_id") or report_info.get("folder")
        for missing in report["completeness"]["missing"]:
            issues.append({
                "report": report_id,
                "report_id": report_info.get("report_id", ""),
                "date": report_info.get("date_raw", ""),
                "folder": report_info.get("folder", ""),
                "code": missing,
                "message": _issue_message(missing),
            })
    return issues


def _source_files(folder_path: Path) -> list[str]:
    names = []
    for name in ("weld_info.json", "GroupWeld.txt", "note.txt", "materials.txt"):
        if (folder_path / name).exists():
            names.append(name)
    for photo in _photo_rows(folder_path, "before") + _photo_rows(folder_path, "after"):
        names.append(photo["name"])
    pdf = find_attachment_pdf(str(folder_path), "") if folder_path.is_dir() else None
    if pdf:
        names.append(os.path.basename(pdf))
    return sorted(set(names))


def _report_status(record: dict[str, Any] | None, folder_path: Path) -> str:
    if record and str(record.get("需重產", "")).strip() == "1":
        return "needs_rebuild"
    if record:
        return "produced"
    if folder_path.is_dir():
        return "unproduced"
    return "missing_folder"


def _infer_change_type(tokens) -> str:
    if not tokens:
        return ""
    return "裁切重焊" if all(token.is_cut for token in tokens) else "加長"


def _is_placeholder_note(note: str) -> bool:
    text = str(note or "").strip()
    if not text:
        return True
    compact = text.replace(" ", "")
    return "請填寫" in compact or compact.startswith("#")


def _issue_message(code: str) -> str:
    return {
        "weld_or_material": "缺少焊口或材料資料",
        "before_photo": "缺少 before 照片",
        "after_photo": "缺少 after 照片",
        "note": "缺少現場 note 或仍是樣板文字",
        "parse_error": "附件資料夾解析失敗",
    }.get(code, code)


def _series_from_folder(folder_name: str) -> str:
    head = str(folder_name).split("_", 1)[0]
    return head.zfill(4) if head.isdigit() else head


def _date_text(date_str: str) -> str:
    text = str(date_str or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def _text(data: dict[str, Any] | None, key: str) -> str:
    if not data:
        return ""
    value = data.get(key, "")
    return "" if value is None else str(value).strip()


def _number_or_text(value: Any) -> Any:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    try:
        num = float(text)
    except (TypeError, ValueError):
        return text
    return int(num) if num == int(num) else num


def _split_weld_code(code: str) -> dict[str, str]:
    text = str(code or "").strip()
    weld_no = ""
    mark = ""
    for idx, ch in enumerate(text):
        if not ch.isdigit():
            weld_no = text[:idx]
            mark = ch
            break
    if not weld_no:
        weld_no = text
    return {"weld_no": weld_no, "mark": mark}


def _photo_sort_key(name: str) -> tuple[str, int, str]:
    stem = Path(name).stem.lower()
    idx = 0
    parts = stem.split("_", 1)
    if len(parts) == 2:
        try:
            idx = int(parts[1])
        except ValueError:
            idx = 0
    return (parts[0], idx, name.lower())
