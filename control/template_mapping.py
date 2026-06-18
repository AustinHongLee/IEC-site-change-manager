# -*- coding: utf-8 -*-
"""
template_mapping.py - CanonicalReport template mapping validation.

This layer is intentionally renderer-neutral. It knows how to validate and
resolve field paths, but it does not draw Excel, PDF, or images.
"""

from __future__ import annotations

import re
from typing import Any

from canonical_fields import list_field_paths


MAPPING_SCHEMA_VERSION = "template_mapping.v1"
MAPPING_TYPES = {"text", "image", "table"}

_SEGMENT_RE = re.compile(r"^(?P<name>[^\[\]]+)(?:\[(?P<selector>\*|\d+|0\.\.n)\])?$")
_NUMERIC_INDEX_RE = re.compile(r"\[(\d+)\]")
_INDEX_SELECTOR_RE = re.compile(r"\[(\d+|0\.\.n)\]")


def validate_template_mapping(
    template: dict[str, Any],
    *,
    field_paths: list[str] | None = None,
) -> dict[str, Any]:
    field_paths = field_paths or list_field_paths()
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(template, dict):
        return {
            "ok": False,
            "errors": ["template 必須是 JSON object"],
            "warnings": [],
            "field_count": 0,
        }

    fields = template.get("fields")
    if not isinstance(fields, list):
        errors.append("fields 必須是陣列")
        fields = []

    for idx, mapping in enumerate(fields, start=1):
        if not isinstance(mapping, dict):
            errors.append(f"fields[{idx}] 必須是 object")
            continue
        mapping_type = str(mapping.get("type", "")).strip()
        source = str(mapping.get("source", "")).strip()
        if mapping_type not in MAPPING_TYPES:
            errors.append(f"fields[{idx}] type 不支援：{mapping_type or '<空白>'}")
            continue
        if not source:
            errors.append(f"fields[{idx}] source 不可空白")
            continue
        if mapping_type == "table":
            _validate_table_mapping(mapping, idx, source, field_paths, errors, warnings)
        else:
            if _has_collection_selector(source):
                errors.append(f"fields[{idx}] {mapping_type} source 不可使用 [*] 或 [0..n]：{source}")
            elif not is_valid_field_path(source, field_paths):
                errors.append(f"fields[{idx}] source 不在 field-path catalog：{source}")

    target_validation = _validate_target_schema(template)
    errors.extend(target_validation.get("errors", []))
    warnings.extend(target_validation.get("warnings", []))

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "field_count": len(fields),
        "target_validation": target_validation,
    }


def is_valid_field_path(path: str, field_paths: list[str] | None = None) -> bool:
    field_paths = field_paths or list_field_paths()
    catalog = set(field_paths)
    normalized = _normalize_path(path)
    if normalized in catalog:
        return True
    wildcard = _INDEX_SELECTOR_RE.sub("[*]", normalized)
    if wildcard in catalog:
        return True
    return any(item.startswith(f"{normalized}[*].") for item in catalog)


def resolve_field_path(data: dict[str, Any], path: str, *, default: Any = "") -> Any:
    parts = _split_field_path(path)
    if not parts:
        return default

    values: list[Any] = [data]
    collected = False
    for part in parts:
        match = _SEGMENT_RE.match(part)
        if not match:
            return default
        name = match.group("name")
        selector = match.group("selector")
        next_values: list[Any] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            child = value.get(name, default)
            if selector is None:
                next_values.append(child)
            elif selector in ("*", "0..n"):
                collected = True
                if isinstance(child, list):
                    next_values.extend(child)
            else:
                if isinstance(child, list):
                    idx = int(selector)
                    if 0 <= idx < len(child):
                        next_values.append(child[idx])
        values = next_values
        if not values:
            return [] if collected else default

    if collected:
        return values
    return values[0] if values else default


def _validate_table_mapping(
    mapping: dict[str, Any],
    idx: int,
    source: str,
    field_paths: list[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not is_valid_field_path(source, field_paths):
        errors.append(f"fields[{idx}] table source 不在 field-path catalog：{source}")
        return
    if _has_numeric_selector(source):
        errors.append(f"fields[{idx}] table source 不可指定單一索引：{source}")
    if not _table_row_limit(mapping):
        errors.append(f"fields[{idx}] table 必須設定 max_rows 或 rows_per_page，避免資料寫過預留版面")

    columns = mapping.get("columns", [])
    if not isinstance(columns, list) or not columns:
        warnings.append(f"fields[{idx}] table 尚未定義 columns")
        return

    for col_idx, column in enumerate(columns, start=1):
        col_source = _column_source(column)
        if not col_source:
            errors.append(f"fields[{idx}].columns[{col_idx}] source 不可空白")
            continue
        full_path = _table_column_full_path(source, col_source)
        if not is_valid_field_path(full_path, field_paths):
            errors.append(f"fields[{idx}].columns[{col_idx}] source 不在 field-path catalog：{col_source}")


def _column_source(column: Any) -> str:
    if isinstance(column, str):
        return column.strip()
    if isinstance(column, dict):
        return str(column.get("source", "")).strip()
    return ""


def _table_column_full_path(source: str, col_source: str) -> str:
    if col_source.startswith(source):
        return col_source
    if source.endswith("[*]") or source.endswith("[0..n]"):
        return f"{source}.{col_source}"
    return f"{source}[*].{col_source}"


def _table_row_limit(mapping: dict[str, Any]) -> int:
    return _positive_int(mapping.get("max_rows") or mapping.get("rows_per_page"))


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _normalize_path(path: str) -> str:
    return str(path or "").strip()


def _split_field_path(path: str) -> list[str]:
    text = str(path or "").strip()
    if not text:
        return []

    parts: list[str] = []
    buffer: list[str] = []
    bracket_depth = 0
    for char in text:
        if char == "." and bracket_depth == 0:
            if buffer:
                parts.append("".join(buffer))
                buffer = []
            continue
        if char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth:
            bracket_depth -= 1
        buffer.append(char)
    if buffer:
        parts.append("".join(buffer))
    return parts


def _has_collection_selector(path: str) -> bool:
    return "[*]" in path or "[0..n]" in path


def _has_numeric_selector(path: str) -> bool:
    return bool(_NUMERIC_INDEX_RE.search(path))


def _validate_target_schema(template: dict[str, Any]) -> dict[str, Any]:
    kind = str(template.get("kind", "") or "").strip()
    if kind != "pdf_overlay":
        return {"ok": True, "errors": [], "warnings": [], "field_count": len(template.get("fields", []) or [])}
    from pdf_overlay_schema import validate_pdf_overlay_template

    return validate_pdf_overlay_template(template)
