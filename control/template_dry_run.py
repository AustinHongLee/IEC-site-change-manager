# -*- coding: utf-8 -*-
"""
template_dry_run.py - Renderer-neutral template dry-run.

The dry-run turns a CanonicalReport plus a validated template into a plain
data summary. It does not create Excel/PDF files.
"""

from __future__ import annotations

import os
import re
from typing import Any

from canonical_fields import list_field_paths
from template_mapping import resolve_field_path, validate_template_mapping


_NUMERIC_INDEX_RE = re.compile(r"\[(\d+|0\.\.n)\]")


def dry_run_template_for_report(report: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    validation = validate_template_mapping(template)
    if not validation["ok"]:
        return {
            "ok": False,
            "validation": validation,
            "placements": [],
            "issues": [{"severity": "error", "code": "template_invalid", "message": "模板驗證未通過"}],
            "summary": _empty_summary(validation.get("field_count", 0)),
        }

    placements: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    counts = {"text": 0, "image": 0, "table": 0}
    for idx, mapping in enumerate(template.get("fields", []) or [], start=1):
        mapping_type = str(mapping.get("type", "")).strip()
        counts[mapping_type] = counts.get(mapping_type, 0) + 1
        if mapping_type == "text":
            placement = _dry_run_text(report, mapping, idx)
        elif mapping_type == "image":
            placement = _dry_run_image(report, mapping, idx)
        elif mapping_type == "table":
            placement = _dry_run_table(report, template, mapping, idx)
        else:
            continue
        placements.append(placement)
        issues.extend(placement.get("issues", []))
    coverage = _analyze_template_coverage(report, template)
    issues.extend(
        _issue("info", "unmapped_data", 0, item["path"], f"資料有值但模板未使用：{item['path']}")
        for item in coverage["unmapped_data"]
    )
    has_errors = any(issue.get("severity") == "error" for issue in issues)

    return {
        "ok": not has_errors,
        "validation": validation,
        "placements": placements,
        "coverage": coverage,
        "issues": issues,
        "summary": {
            "field_count": len(template.get("fields", []) or []),
            "text_count": counts.get("text", 0),
            "image_count": counts.get("image", 0),
            "table_count": counts.get("table", 0),
            "unmapped_data_count": coverage["unmapped_count"],
            "issue_count": len(issues),
        },
    }


def dry_run_template_for_report_set(report_set: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    reports = report_set.get("reports", []) or []
    report_results = []
    all_issues: list[dict[str, Any]] = []
    for report in reports:
        result = dry_run_template_for_report(report, template)
        report_label = (
            report.get("report", {}).get("report_id")
            or report.get("report", {}).get("folder")
            or ""
        )
        result["report"] = report_label
        report_results.append(result)
        for issue in result.get("issues", []):
            issue_with_report = dict(issue)
            issue_with_report["report"] = report_label
            all_issues.append(issue_with_report)

    return {
        "ok": all(result.get("ok") for result in report_results),
        "report_count": len(reports),
        "reports": report_results,
        "issues": all_issues,
        "summary": {
            "report_count": len(reports),
            "issue_count": len(all_issues),
        },
    }


def _dry_run_text(report: dict[str, Any], mapping: dict[str, Any], idx: int) -> dict[str, Any]:
    source = str(mapping.get("source", "")).strip()
    value = resolve_field_path(report, source)
    issues = []
    if _is_missing_value(value):
        issues.append(_issue("warning", "missing_text_value", idx, source, "文字欄位沒有值"))
    return {
        "index": idx,
        "type": "text",
        "source": source,
        "target": _target_hint(mapping),
        "value": value,
        "is_missing": _is_missing_value(value),
        "issues": issues,
    }


def _dry_run_image(report: dict[str, Any], mapping: dict[str, Any], idx: int) -> dict[str, Any]:
    source = str(mapping.get("source", "")).strip()
    value = resolve_field_path(report, source)
    path = _image_path(value)
    exists = bool(path and os.path.exists(path))
    issues = []
    if not path:
        issues.append(_issue("warning", "missing_image_value", idx, source, "圖片欄位沒有路徑"))
    elif not exists:
        issues.append(_issue("warning", "missing_image_file", idx, source, f"圖片檔不存在：{path}"))
    return {
        "index": idx,
        "type": "image",
        "source": source,
        "target": _target_hint(mapping),
        "path": path,
        "exists": exists,
        "issues": issues,
    }


def _dry_run_table(report: dict[str, Any], template: dict[str, Any], mapping: dict[str, Any], idx: int) -> dict[str, Any]:
    source = str(mapping.get("source", "")).strip()
    rows = resolve_field_path(report, source, default=[])
    rows = rows if isinstance(rows, list) else []
    row_count = len(rows)
    max_rows = _positive_int(mapping.get("max_rows") or mapping.get("rows_per_page"))
    overflow_count = max(0, row_count - max_rows) if max_rows else 0
    overflow = str(mapping.get("overflow") or "error").strip()
    is_pdf_overlay = str(template.get("kind", "")).strip() == "pdf_overlay"
    render_pages = _table_render_pages(row_count, max_rows, overflow, is_pdf_overlay)
    issues = []
    if row_count == 0:
        issues.append(_issue("warning", "empty_table", idx, source, "表格沒有資料列"))
    if overflow_count:
        if is_pdf_overlay and overflow == "new_page":
            pass
        elif is_pdf_overlay and overflow == "truncate":
            issues.append(
                _issue(
                    "error",
                    "overflow_mode_unsupported",
                    idx,
                    source,
                    f"pdf_overlay table overflow={overflow} 尚未支援；資料 {row_count} 列超過預留 {max_rows} 列",
                )
            )
        else:
            issues.append(
                _issue(
                    "error",
                    "table_overflow",
                    idx,
                    source,
                    f"表格資料 {row_count} 列超過預留 {max_rows} 列，超出 {overflow_count} 列",
                )
            )
    table_image = _dry_run_table_image_cells(rows, mapping, idx, source)
    issues.extend(table_image["issues"])
    return {
        "index": idx,
        "type": "table",
        "source": source,
        "target": _target_hint(mapping),
        "row_count": row_count,
        "max_rows": max_rows,
        "overflow_count": overflow_count,
        "overflow": overflow,
        "render_pages": render_pages,
        "image_cell_count": table_image["image_cell_count"],
        "columns": [_column_source(column) for column in mapping.get("columns", []) or []],
        "issues": issues,
    }


def _analyze_template_coverage(report: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    covered = _covered_field_paths(template)
    ignored = {_normalize_path(path) for path in template.get("coverage_ignore", []) or []}
    unmapped = []
    for path in list_field_paths():
        normalized = _normalize_path(path)
        if _is_collection_root(path) or normalized in ignored:
            continue
        if normalized in covered:
            continue
        value = resolve_field_path(report, path, default="")
        if not _has_meaningful_value(value):
            continue
        unmapped.append({
            "path": path,
            "value_preview": _preview_value(value),
        })
    return {
        "covered_paths": sorted(covered),
        "ignored_paths": sorted(ignored),
        "unmapped_data": unmapped,
        "unmapped_count": len(unmapped),
    }


def _covered_field_paths(template: dict[str, Any]) -> set[str]:
    covered: set[str] = set()
    for mapping in template.get("fields", []) or []:
        if not isinstance(mapping, dict):
            continue
        mapping_type = str(mapping.get("type", "")).strip()
        source = str(mapping.get("source", "")).strip()
        if not source:
            continue
        if mapping_type == "table":
            for column in mapping.get("columns", []) or []:
                column_source = _column_source(column)
                if not column_source:
                    continue
                full_path = column_source if column_source.startswith(source) else f"{source}[*].{column_source}"
                covered.add(_normalize_path(full_path))
        else:
            covered.add(_normalize_path(source))
    return covered


def _is_collection_root(path: str) -> bool:
    if path.endswith("[*]") or path.endswith("[0..n]"):
        return True
    return path in {"welds.rows", "materials.rows", "photos.before", "photos.after"}


def _normalize_path(path: str) -> str:
    return _NUMERIC_INDEX_RE.sub("[*]", str(path or "").strip())


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, list):
        return any(_has_meaningful_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_meaningful_value(item) for item in value.values())
    return True


def _preview_value(value: Any) -> str:
    if isinstance(value, list):
        preview = "、".join(str(item) for item in value[:3])
        if len(value) > 3:
            preview += f"…(+{len(value) - 3})"
        return preview
    text = str(value)
    return text if len(text) <= 80 else text[:77] + "..."


def _image_path(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("path", "") or "").strip()
    return str(value or "").strip()


def _dry_run_table_image_cells(
    rows: list[Any],
    mapping: dict[str, Any],
    idx: int,
    source: str,
) -> dict[str, Any]:
    issues = []
    image_cell_count = 0
    for column in mapping.get("columns", []) or []:
        if _column_cell_type(column) != "image":
            continue
        column_source = _column_source(column)
        issue_source = _table_column_issue_source(source, column_source)
        for row in rows:
            image_cell_count += 1
            value = resolve_field_path(row, column_source)
            path = _image_path(value)
            if not path:
                issues.append(_issue("warning", "missing_image_value", idx, issue_source, "圖片欄位沒有路徑"))
            elif not os.path.exists(path):
                issues.append(_issue("warning", "missing_image_file", idx, issue_source, f"圖片檔不存在：{path}"))
    return {"image_cell_count": image_cell_count, "issues": issues}


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _target_hint(mapping: dict[str, Any]) -> str:
    for key in ("cell", "anchor", "start_cell", "rect", "rect_norm", "region_norm"):
        if key in mapping:
            return str(mapping.get(key, ""))
    return ""


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _table_render_pages(row_count: int, max_rows: int, overflow: str, is_pdf_overlay: bool) -> int:
    if not is_pdf_overlay or overflow != "new_page" or max_rows <= 0:
        return 1
    return max(1, (row_count + max_rows - 1) // max_rows)


def _column_source(column: Any) -> str:
    if isinstance(column, str):
        return column.strip()
    if isinstance(column, dict):
        return str(column.get("source", "")).strip()
    return ""


def _column_cell_type(column: Any) -> str:
    if isinstance(column, dict):
        return str(column.get("cell_type") or column.get("type") or "text").strip()
    return "text"


def _table_column_issue_source(source: str, column_source: str) -> str:
    if not source or not column_source:
        return source or column_source
    if column_source.startswith(source):
        return column_source
    if source.endswith("[*]") or source.endswith("[0..n]"):
        return f"{source}.{column_source}"
    return f"{source}[*].{column_source}"


def _issue(severity: str, code: str, idx: int, source: str, message: str) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "field_index": idx,
        "source": source,
        "message": message,
    }


def _empty_summary(field_count: int) -> dict[str, int]:
    return {
        "field_count": field_count,
        "text_count": 0,
        "image_count": 0,
        "table_count": 0,
        "unmapped_data_count": 0,
        "issue_count": 1,
    }
