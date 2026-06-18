# -*- coding: utf-8 -*-
"""PDF overlay target-schema validation.

This module validates renderer-specific target fields for ``kind=pdf_overlay``.
It deliberately does not render PDFs; the shared source mapping still lives in
``template_mapping``.
"""

from __future__ import annotations

from typing import Any


PDF_OVERLAY_KIND = "pdf_overlay"
PDF_OVERLAY_SCHEMA_VERSION = "pdf_overlay.v1"

XLSX_TARGET_KEYS = {
    "anchor",
    "cell",
    "max_height_px",
    "max_width_px",
    "sheet",
    "size_cells",
    "start_cell",
    "workbook",
}
TEXT_ALIGN = {"left", "center", "right"}
TEXT_VALIGN = {"top", "middle", "bottom"}
TEXT_OVERFLOW = {"error", "shrink", "clip", "wrap"}
IMAGE_FIT = {"contain", "cover", "stretch"}
TABLE_OVERFLOW = {"error", "new_page", "truncate"}
TABLE_CELL_TYPES = {"text", "image"}


def validate_pdf_overlay_template(template: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    fields = template.get("fields") if isinstance(template, dict) else []
    fields = fields if isinstance(fields, list) else []

    if not isinstance(template, dict):
        return _result(errors=["template 必須是 JSON object"], warnings=[], field_count=0)

    kind = _text(template.get("kind"))
    if kind != PDF_OVERLAY_KIND:
        return _result(errors=[], warnings=[], field_count=len(fields))

    target_schema = _text(
        template.get("target_schema_version")
        or template.get("pdf_overlay_schema_version")
        or PDF_OVERLAY_SCHEMA_VERSION
    )
    if target_schema != PDF_OVERLAY_SCHEMA_VERSION:
        errors.append(f"pdf_overlay target_schema_version 不支援：{target_schema or '<空白>'}")

    coordinate_space = _text(template.get("coordinate_space") or "normalized")
    if coordinate_space != "normalized":
        errors.append("pdf_overlay coordinate_space 目前只支援 normalized")

    base_pdf = _text(template.get("base_pdf") or template.get("template_pdf"))
    page_size = template.get("page_size")
    if not base_pdf and not page_size:
        errors.append("pdf_overlay 必須指定 base_pdf/template_pdf 或 page_size，renderer 才能取得頁面尺寸")

    regions: list[dict[str, Any]] = []
    for idx, mapping in enumerate(fields, start=1):
        if not isinstance(mapping, dict):
            continue
        mapping_type = _text(mapping.get("type"))
        if mapping_type not in {"text", "image", "table"}:
            continue
        _validate_no_xlsx_target(mapping, idx, errors)
        page = _validate_page(mapping, idx, errors)
        rect = _validate_rect_norm(mapping, idx, errors)
        if page and rect:
            regions.append({"field_index": idx, "page": page, "rect": rect})

        if mapping_type == "text":
            _validate_text_target(mapping, idx, errors, warnings)
        elif mapping_type == "image":
            _validate_image_target(mapping, idx, errors)
        elif mapping_type == "table":
            _validate_table_target(mapping, idx, errors, warnings)

    _validate_region_overlap(regions, errors)
    return _result(errors=errors, warnings=warnings, field_count=len(fields))


def _validate_no_xlsx_target(mapping: dict[str, Any], idx: int, errors: list[str]) -> None:
    keys = sorted(key for key in mapping if key in XLSX_TARGET_KEYS)
    if keys:
        errors.append(f"fields[{idx}] pdf_overlay 不可使用 Excel 落點欄位：{', '.join(keys)}")


def _validate_page(mapping: dict[str, Any], idx: int, errors: list[str]) -> int:
    page = _positive_int(mapping.get("page"))
    if page <= 0:
        errors.append(f"fields[{idx}] pdf_overlay page 必須是正整數")
    return page


def _validate_rect_norm(mapping: dict[str, Any], idx: int, errors: list[str]) -> tuple[float, float, float, float] | None:
    rect = mapping.get("rect_norm")
    if not isinstance(rect, list) or len(rect) != 4:
        errors.append(f"fields[{idx}] pdf_overlay 必須設定 rect_norm: [x, y, width, height]")
        return None
    values = []
    for item in rect:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            errors.append(f"fields[{idx}] rect_norm 必須全為數字")
            return None
    x, y, width, height = values
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        errors.append(f"fields[{idx}] rect_norm 座標不可為負，width/height 必須大於 0")
        return None
    if x > 1 or y > 1 or width > 1 or height > 1 or x + width > 1 or y + height > 1:
        errors.append(f"fields[{idx}] rect_norm 必須落在 0..1 頁面範圍內")
        return None
    return x, y, width, height


def _validate_text_target(
    mapping: dict[str, Any],
    idx: int,
    errors: list[str],
    warnings: list[str],
) -> None:
    _validate_choice(mapping, idx, "align", TEXT_ALIGN, errors)
    _validate_choice(mapping, idx, "valign", TEXT_VALIGN, errors)
    if not _text(mapping.get("overflow")):
        warnings.append(f"fields[{idx}] text 未指定 overflow，renderer 將預設 error")
    _validate_choice(mapping, idx, "overflow", TEXT_OVERFLOW, errors)
    font_size = _positive_float(mapping.get("font_size"))
    min_font_size = _positive_float(mapping.get("min_font_size"))
    if "font_size" in mapping and font_size <= 0:
        errors.append(f"fields[{idx}] font_size 必須大於 0")
    if "min_font_size" in mapping and min_font_size <= 0:
        errors.append(f"fields[{idx}] min_font_size 必須大於 0")
    if font_size > 0 and min_font_size > 0 and min_font_size > font_size:
        errors.append(f"fields[{idx}] min_font_size 不可大於 font_size")


def _validate_image_target(mapping: dict[str, Any], idx: int, errors: list[str]) -> None:
    _validate_choice(mapping, idx, "fit", IMAGE_FIT, errors)


def _validate_table_target(
    mapping: dict[str, Any],
    idx: int,
    errors: list[str],
    warnings: list[str],
) -> None:
    rows_per_page = _positive_int(mapping.get("rows_per_page") or mapping.get("max_rows"))
    if rows_per_page <= 0:
        errors.append(f"fields[{idx}] table 必須設定 rows_per_page 或 max_rows")
    if not _text(mapping.get("overflow")):
        warnings.append(f"fields[{idx}] table 未指定 overflow，renderer 將預設 error")
    _validate_choice(mapping, idx, "overflow", TABLE_OVERFLOW, errors)
    if "continuation_page" in mapping and _positive_int(mapping.get("continuation_page")) <= 0:
        errors.append(f"fields[{idx}] continuation_page 必須是正整數")
    if "row_height_pt" in mapping and _positive_float(mapping.get("row_height_pt")) <= 0:
        errors.append(f"fields[{idx}] row_height_pt 必須大於 0")
    if "header_height_pt" in mapping and _positive_float(mapping.get("header_height_pt")) <= 0:
        errors.append(f"fields[{idx}] header_height_pt 必須大於 0")

    widths = []
    for col_idx, column in enumerate(mapping.get("columns", []) or [], start=1):
        if not isinstance(column, dict):
            continue
        cell_type = _text(column.get("cell_type") or column.get("type") or "text")
        if cell_type not in TABLE_CELL_TYPES:
            errors.append(f"fields[{idx}].columns[{col_idx}] cell_type 不支援：{cell_type or '<空白>'}")
        fit = _text(column.get("fit"))
        if fit and fit not in IMAGE_FIT:
            errors.append(f"fields[{idx}].columns[{col_idx}] fit 不支援：{fit}")
        if "width_norm" in column:
            width = _positive_float(column.get("width_norm"))
            if width <= 0:
                errors.append(f"fields[{idx}].columns[{col_idx}] width_norm 必須大於 0")
            widths.append(width)
    if widths and sum(widths) > 1.000001:
        errors.append(f"fields[{idx}] table columns width_norm 總和不可超過 1")


def _validate_choice(
    mapping: dict[str, Any],
    idx: int,
    key: str,
    choices: set[str],
    errors: list[str],
) -> None:
    value = _text(mapping.get(key))
    if value and value not in choices:
        errors.append(f"fields[{idx}] {key} 不支援：{value}")


def _validate_region_overlap(regions: list[dict[str, Any]], errors: list[str]) -> None:
    for left_idx, left in enumerate(regions):
        for right in regions[left_idx + 1:]:
            if left["page"] != right["page"]:
                continue
            if _rects_overlap(left["rect"], right["rect"]):
                errors.append(
                    f"fields[{left['field_index']}] 與 fields[{right['field_index']}] pdf_overlay rect_norm 重疊"
                )


def _rects_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    left_x, left_y, left_w, left_h = left
    right_x, right_y, right_w, right_h = right
    return not (
        left_x + left_w <= right_x
        or right_x + right_w <= left_x
        or left_y + left_h <= right_y
        or right_y + right_h <= left_y
    )


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _positive_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _result(*, errors: list[str], warnings: list[str], field_count: int) -> dict[str, Any]:
    return {
        "ok": not errors,
        "schema_version": PDF_OVERLAY_SCHEMA_VERSION,
        "errors": errors,
        "warnings": warnings,
        "field_count": field_count,
    }
