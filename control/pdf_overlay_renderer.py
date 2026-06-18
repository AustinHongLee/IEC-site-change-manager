# -*- coding: utf-8 -*-
"""Minimal PDF overlay renderer for CanonicalReport templates."""

from __future__ import annotations

import copy
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from output_result import attach_output_envelope, output_item, step_item
from template_dry_run import dry_run_template_for_report
from template_mapping import resolve_field_path


PDF_MAX_PAGE_GUARD = 200


def render_pdf_overlay_for_report(
    report: dict[str, Any],
    template: dict[str, Any],
    output_path: str | os.PathLike[str],
    *,
    template_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    dry_run = dry_run_template_for_report(report, template)
    if not dry_run["ok"]:
        return attach_output_envelope({
            "ok": False,
            "path": "",
            "dry_run": dry_run,
            "summary": _empty_summary(),
            "issues": list(dry_run.get("issues", [])),
        })

    try:
        from pypdf import PdfReader, PdfWriter
    except Exception as exc:
        return _dependency_failure("pypdf", exc)

    base_result = _load_base_pdf(template, template_dir=template_dir)
    if not base_result["ok"]:
        return attach_output_envelope({
            "ok": False,
            "path": "",
            "dry_run": dry_run,
            "summary": _empty_summary(),
            "issues": base_result["issues"],
        })

    try:
        reader = PdfReader(base_result["stream"])
    except Exception as exc:
        return attach_output_envelope({
            "ok": False,
            "path": "",
            "dry_run": dry_run,
            "summary": _empty_summary(),
            "issues": [_issue("error", "base_pdf_unreadable", f"無法讀取 base PDF：{exc}")],
        })

    page_count = len(reader.pages)
    render_plan = _build_render_plan(report, template, page_count)
    if not render_plan["ok"]:
        return attach_output_envelope({
            "ok": False,
            "path": "",
            "dry_run": dry_run,
            "summary": _empty_summary(),
            "issues": render_plan["issues"],
        })

    writer = PdfWriter()
    result = {
        "ok": True,
        "path": str(output_path),
        "dry_run": dry_run,
        "summary": _empty_summary(),
        "issues": list(dry_run.get("issues", [])),
        "base_pdf": base_result.get("path", ""),
    }

    for job in render_plan["jobs"]:
        page = _copy_base_page(reader, job["base_page"])
        writer.add_page(page)
        target_page = writer.pages[-1]
        fields = job["fields"]
        if fields:
            overlay_result = _build_overlay_pdf_page(report, template, target_page, fields)
            result["issues"].extend(overlay_result["issues"])
            _add_summary(result["summary"], overlay_result["summary"])
            if overlay_result["ok"]:
                overlay_reader = PdfReader(BytesIO(overlay_result["pdf_bytes"]))
                target_page.merge_page(overlay_reader.pages[0])
            else:
                result["ok"] = False

    if not result["ok"]:
        result["path"] = ""
        return attach_output_envelope(result)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    try:
        with open(tmp, "wb") as f:
            writer.write(f)
        os.replace(tmp, output)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

    validation = _validate_pdf(output)
    result["pdf_validation"] = validation
    if not validation["ok"]:
        result["ok"] = False
        result["path"] = ""
        result["issues"].append(validation["issue"])

    return attach_output_envelope(
        result,
        outputs=[output_item(kind="pdf_overlay", path=result.get("path", ""), role="primary", label="PDF overlay")],
        steps=[
            step_item(key="pdf_overlay_dry_run", ok=dry_run["ok"], label="Validate source mapping and target schema"),
            step_item(key="pdf_overlay_render", ok=result["ok"], label="Render PDF overlay"),
            step_item(key="pdf_validation", ok=validation.get("ok", False), label="PDF readable validation"),
        ],
    )


def _build_overlay_pdf_page(
    report: dict[str, Any],
    template: dict[str, Any],
    page,
    fields: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        from reportlab.pdfgen import canvas
    except Exception as exc:
        return {
            "ok": False,
            "pdf_bytes": b"",
            "summary": _empty_summary(),
            "issues": [_issue("error", "renderer_dependency_missing", f"缺少 reportlab：{exc}")],
        }

    geometry = _page_geometry(page)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(geometry["media_width"], geometry["media_height"]))
    issues: list[dict[str, Any]] = []
    summary = _empty_summary()
    debug = bool(template.get("debug", False))

    for idx, mapping in fields:
        mapping = dict(mapping)
        mapping["_field_index"] = idx
        rect = _rect_to_points(mapping, geometry)
        if debug or bool(mapping.get("debug", False)):
            _draw_debug_rect(c, rect)
        mapping_type = str(mapping.get("type", "")).strip()
        if mapping_type == "text":
            rendered = _render_text(c, report, template, mapping, rect)
            issues.extend(rendered["issues"])
            summary["text"] += 1
        elif mapping_type == "image":
            rendered = _render_image(c, report, mapping, rect)
            issues.extend(rendered["issues"])
            summary["image"] += 1
        elif mapping_type == "table":
            rendered = _render_table(c, report, mapping, rect)
            issues.extend(rendered["issues"])
            summary["table"] += 1
            summary["image"] += rendered.get("images", 0)
            summary["rows"] += rendered.get("rows", 0)

    c.save()
    return {
        "ok": not any(issue.get("severity") == "error" for issue in issues),
        "pdf_bytes": buffer.getvalue(),
        "summary": summary,
        "issues": issues,
    }


def _build_render_plan(report: dict[str, Any], template: dict[str, Any], page_count: int) -> dict[str, Any]:
    fields_by_page = _group_fields_by_page(template)
    issues = [
        _issue("error", "pdf_overlay_page_out_of_range", f"fields page={page} 超出 base PDF 頁數 {page_count}")
        for page in sorted(fields_by_page)
        if page < 1 or page > page_count
    ]
    if issues:
        return {"ok": False, "jobs": [], "issues": issues}

    jobs: list[dict[str, Any]] = []
    for page_index in range(1, page_count + 1):
        fields = fields_by_page.get(page_index, [])
        first_page_fields: list[tuple[int, dict[str, Any]]] = []
        continuation_jobs: list[dict[str, Any]] = []
        for field_index, mapping in fields:
            if str(mapping.get("type", "")).strip() != "table":
                first_page_fields.append((field_index, mapping))
                continue
            expanded = _expand_table_mapping(report, field_index, mapping, page_index, page_count)
            issues.extend(expanded["issues"])
            chunks = expanded["chunks"]
            if chunks:
                first_page_fields.append((field_index, chunks[0]["mapping"]))
                continuation_jobs.extend(
                    {"base_page": chunk["base_page"], "fields": [(field_index, chunk["mapping"])]}
                    for chunk in chunks[1:]
                )
        jobs.append({"base_page": page_index, "fields": first_page_fields})
        jobs.extend(continuation_jobs)

    if len(jobs) > PDF_MAX_PAGE_GUARD:
        issues.append(_issue("error", "pdf_overlay_page_guard", f"輸出頁數過大：{len(jobs)}"))
    return {"ok": not any(issue.get("severity") == "error" for issue in issues), "jobs": jobs, "issues": issues}


def _expand_table_mapping(
    report: dict[str, Any],
    field_index: int,
    mapping: dict[str, Any],
    page_index: int,
    page_count: int,
) -> dict[str, Any]:
    rows = resolve_field_path(report, str(mapping.get("source", "")).strip(), default=[])
    rows = rows if isinstance(rows, list) else []
    row_limit = _positive_int(mapping.get("rows_per_page") or mapping.get("max_rows"))
    overflow = str(mapping.get("overflow") or "error").strip()
    issues: list[dict[str, Any]] = []

    if not row_limit or len(rows) <= row_limit:
        return {"chunks": [{"base_page": page_index, "mapping": _table_chunk(mapping, rows)}], "issues": issues}

    if overflow != "new_page":
        code = "overflow_mode_unsupported" if overflow == "truncate" else "table_overflow"
        message = (
            f"pdf_overlay table overflow={overflow} 尚未支援；目前不會截斷後產出"
            if overflow == "truncate"
            else f"表格資料 {len(rows)} 列超過預留 {row_limit} 列"
        )
        issue = _field_issue("error", code, {"_field_index": field_index, **mapping}, message)
        return {"chunks": [{"base_page": page_index, "mapping": _table_chunk(mapping, rows[:row_limit])}], "issues": [issue]}

    continuation_page = _positive_int(mapping.get("continuation_page")) or page_index
    if continuation_page < 1 or continuation_page > page_count:
        issue = _field_issue(
            "error",
            "pdf_overlay_page_out_of_range",
            {"_field_index": field_index, **mapping},
            f"continuation_page={continuation_page} 超出 base PDF 頁數 {page_count}",
        )
        return {"chunks": [], "issues": [issue]}

    chunks = []
    for chunk_index, start in enumerate(range(0, len(rows), row_limit), start=1):
        base_page = page_index if chunk_index == 1 else continuation_page
        chunk = rows[start:start + row_limit]
        chunks.append({
            "base_page": base_page,
            "mapping": _table_chunk(
                mapping,
                chunk,
                chunk_index=chunk_index,
                chunk_count=(len(rows) + row_limit - 1) // row_limit,
                total_rows=len(rows),
            ),
        })
    return {"chunks": chunks, "issues": issues}


def _table_chunk(
    mapping: dict[str, Any],
    rows: list[Any],
    *,
    chunk_index: int = 1,
    chunk_count: int = 1,
    total_rows: int | None = None,
) -> dict[str, Any]:
    chunk = dict(mapping)
    chunk["_rows_override"] = list(rows)
    chunk["_chunk_index"] = chunk_index
    chunk["_chunk_count"] = chunk_count
    chunk["_total_rows"] = len(rows) if total_rows is None else total_rows
    return chunk


def _render_text(c, report: dict[str, Any], template: dict[str, Any], mapping: dict[str, Any], rect: dict[str, float]) -> dict[str, Any]:
    from reportlab.pdfbase import pdfmetrics

    value = _cell_value(resolve_field_path(report, str(mapping.get("source", "")).strip()))
    preferred_font = str(mapping.get("font") or template.get("defaults", {}).get("font") or "")
    font_name = _font_name(preferred_font or ("STSong-Light" if _has_non_ascii(value) else "Helvetica"))
    font_size = _positive_float(mapping.get("font_size") or template.get("defaults", {}).get("size")) or 10.0
    min_font_size = _positive_float(mapping.get("min_font_size")) or max(6.0, font_size - 4.0)
    overflow = str(mapping.get("overflow") or template.get("defaults", {}).get("overflow") or "error").strip()
    align = str(mapping.get("align") or "left").strip()
    valign = str(mapping.get("valign") or "top").strip()
    if overflow not in {"error", "shrink", "clip", "wrap"}:
        return {
            "issues": [
                _field_issue(
                    "error",
                    "overflow_mode_unsupported",
                    mapping,
                    f"text overflow 模式尚未支援：{overflow or '<空白>'}",
                )
            ]
        }

    size = font_size
    lines = _wrap_text(value, rect["width"], font_name, size)
    while overflow == "shrink" and size > min_font_size and _lines_height(lines, size) > rect["height"]:
        size -= 0.5
        lines = _wrap_text(value, rect["width"], font_name, size)

    max_lines = max(1, int(rect["height"] // (size * 1.2)))
    width_overflow = any(pdfmetrics.stringWidth(line, font_name, size) > rect["width"] + 0.01 for line in lines)
    if len(lines) > max_lines:
        if overflow == "error":
            return {
                "issues": [
                    _field_issue(
                        "error",
                        "text_overflow",
                        mapping,
                        f"文字欄位超出 PDF 區塊：需要 {len(lines)} 行，預留 {max_lines} 行",
                    )
                ]
            }
        lines = lines[:max_lines]
        if overflow in {"clip", "shrink", "wrap"} and lines:
            lines[-1] = _ellipsize(lines[-1], rect["width"], font_name, size)
    elif overflow == "error" and width_overflow:
        return {
            "issues": [
                _field_issue(
                    "error",
                    "text_overflow",
                    mapping,
                    "文字欄位寬度超出 PDF 區塊",
                )
            ]
        }

    total_height = _lines_height(lines, size)
    if valign == "middle":
        y = rect["bottom"] + (rect["height"] + total_height) / 2 - size
    elif valign == "bottom":
        y = rect["bottom"] + total_height - size
    else:
        y = rect["bottom"] + rect["height"] - size

    c.setFont(font_name, size)
    for line in lines:
        text_width = pdfmetrics.stringWidth(line, font_name, size)
        if align == "center":
            x = rect["left"] + (rect["width"] - text_width) / 2
        elif align == "right":
            x = rect["left"] + rect["width"] - text_width
        else:
            x = rect["left"]
        c.drawString(x, y, line)
        y -= size * 1.2
    return {"issues": []}


def _render_image(c, report: dict[str, Any], mapping: dict[str, Any], rect: dict[str, float]) -> dict[str, Any]:
    value = resolve_field_path(report, str(mapping.get("source", "")).strip())
    return _draw_image_value(c, value, mapping, rect)


def _draw_image_value(c, value: Any, mapping: dict[str, Any], rect: dict[str, float]) -> dict[str, Any]:
    from reportlab.lib.utils import ImageReader

    path = _image_path(value)
    if not path:
        _draw_placeholder(c, rect, "missing image")
        return {"issues": [_field_issue("warning", "missing_image_value", mapping, "圖片欄位沒有路徑")]}
    if not os.path.exists(path):
        _draw_placeholder(c, rect, "image not found")
        return {"issues": [_field_issue("warning", "missing_image_file", mapping, f"圖片檔不存在：{path}")]}
    try:
        image = ImageReader(path)
        image_width, image_height = image.getSize()
    except Exception as exc:
        _draw_placeholder(c, rect, "unreadable image")
        return {"issues": [_field_issue("warning", "unreadable_image_file", mapping, f"無法讀取圖片：{path}：{exc}")]}

    fit = str(mapping.get("fit") or "contain").strip()
    if fit == "stretch":
        draw_rect = rect
    else:
        scale = _image_scale(image_width, image_height, rect["width"], rect["height"], cover=(fit == "cover"))
        width = image_width * scale
        height = image_height * scale
        draw_rect = {
            "left": rect["left"] + (rect["width"] - width) / 2,
            "bottom": rect["bottom"] + (rect["height"] - height) / 2,
            "width": width,
            "height": height,
        }
    c.saveState()
    clip = c.beginPath()
    clip.rect(rect["left"], rect["bottom"], rect["width"], rect["height"])
    c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(image, draw_rect["left"], draw_rect["bottom"], draw_rect["width"], draw_rect["height"], mask="auto")
    c.restoreState()
    return {"issues": []}


def _render_table(c, report: dict[str, Any], mapping: dict[str, Any], rect: dict[str, float]) -> dict[str, Any]:
    rows = mapping.get("_rows_override")
    if rows is None:
        rows = resolve_field_path(report, str(mapping.get("source", "")).strip(), default=[])
    rows = rows if isinstance(rows, list) else []
    row_limit = _positive_int(mapping.get("rows_per_page") or mapping.get("max_rows"))
    visible_rows = rows[:row_limit] if row_limit else rows
    issues: list[dict[str, Any]] = []
    if "_rows_override" not in mapping and row_limit and len(rows) > row_limit:
        overflow = str(mapping.get("overflow") or "error").strip()
        if overflow == "new_page":
            issues.append(
                _field_issue(
                    "error",
                    "table_overflow",
                    mapping,
                    "table overflow=new_page 應由 render plan 展開，renderer 收到未分頁資料",
                )
            )
        elif overflow == "truncate":
            issues.append(
                _field_issue(
                    "error",
                    "overflow_mode_unsupported",
                    mapping,
                    f"pdf_overlay table overflow={overflow} 尚未支援；目前不會續頁或截斷後產出",
                )
            )
        else:
            issues.append(_field_issue("error", "table_overflow", mapping, f"表格資料 {len(rows)} 列超過預留 {row_limit} 列"))

    columns = mapping.get("columns", []) or []
    if not columns:
        return {"rows": 0, "images": 0, "issues": issues}

    font = _font_name("STSong-Light")
    font_size = _positive_float(mapping.get("font_size")) or 8.0
    header = bool(mapping.get("write_header", True))
    default_row_count = len(visible_rows) + (1 if header else 0)
    row_height = _positive_float(mapping.get("row_height_pt")) or min(16.0, rect["height"] / max(1, default_row_count))
    header_height = _positive_float(mapping.get("header_height_pt")) or row_height
    table_height = row_height * len(visible_rows) + (header_height if header else 0)
    if table_height > rect["height"] + 0.01:
        issues.append(
            _field_issue(
                "error",
                "table_row_height_overflow",
                mapping,
                f"表格 rows_per_page/row_height_pt 超出 PDF 區塊高度：需要 {table_height:.1f}pt，預留 {rect['height']:.1f}pt",
            )
        )
        return {"rows": 0, "images": 0, "issues": issues}
    widths = _column_widths(columns, rect["width"])

    y_top = rect["bottom"] + rect["height"]
    image_count = 0
    c.setStrokeColorRGB(0.70, 0.74, 0.78)
    c.setLineWidth(0.4)
    c.setFont(font, font_size)
    if header:
        _draw_table_row(c, rect["left"], y_top - header_height, header_height, widths, [_column_header(col) for col in columns], font, font_size, fill=True)
        y_top -= header_height
    for row in visible_rows:
        rendered_row = _draw_table_data_row(c, row, mapping, rect["left"], y_top - row_height, row_height, widths, columns, font, font_size)
        issues.extend(rendered_row["issues"])
        image_count += rendered_row["images"]
        y_top -= row_height
    return {"rows": len(visible_rows), "images": image_count, "issues": issues}


def _draw_table_row(c, left: float, bottom: float, height: float, widths: list[float], values: list[str], font: str, font_size: float, *, fill: bool) -> None:
    x = left
    if fill:
        c.saveState()
        c.setFillColorRGB(0.93, 0.95, 0.97)
        c.rect(left, bottom, sum(widths), height, stroke=0, fill=1)
        c.restoreState()
    for width, value in zip(widths, values):
        c.rect(x, bottom, width, height, stroke=1, fill=0)
        text = _ellipsize(value, max(1, width - 4), font, font_size)
        c.drawString(x + 2, bottom + max(2, (height - font_size) / 2), text)
        x += width


def _draw_table_data_row(
    c,
    row: Any,
    mapping: dict[str, Any],
    left: float,
    bottom: float,
    height: float,
    widths: list[float],
    columns: list[Any],
    font: str,
    font_size: float,
) -> dict[str, Any]:
    x = left
    issues: list[dict[str, Any]] = []
    image_count = 0
    for width, column in zip(widths, columns):
        c.rect(x, bottom, width, height, stroke=1, fill=0)
        source = _column_source(column)
        value = resolve_field_path(row, source)
        if _column_cell_type(column) == "image":
            image_count += 1
            cell_mapping = dict(mapping)
            cell_mapping["source"] = _table_column_issue_source(mapping, source)
            cell_mapping["fit"] = _column_fit(column)
            rendered = _draw_image_value(c, value, cell_mapping, _inset_rect({
                "left": x,
                "bottom": bottom,
                "width": width,
                "height": height,
            }, 2.0))
            issues.extend(rendered["issues"])
        else:
            text = _ellipsize(_cell_value(value), max(1, width - 4), font, font_size)
            c.drawString(x + 2, bottom + max(2, (height - font_size) / 2), text)
        x += width
    return {"issues": issues, "images": image_count}


def _load_base_pdf(template: dict[str, Any], *, template_dir: str | os.PathLike[str] | None) -> dict[str, Any]:
    base_pdf = str(template.get("base_pdf") or template.get("template_pdf") or "").strip()
    if base_pdf:
        path = Path(base_pdf)
        if not path.is_absolute() and template_dir:
            path = Path(template_dir) / path
        if not path.exists():
            return {"ok": False, "stream": None, "issues": [_issue("error", "base_pdf_missing", f"找不到 base PDF：{path}")]}
        return {"ok": True, "stream": str(path), "path": str(path)}

    page_size = template.get("page_size")
    size = _page_size(page_size)
    if not size:
        return {"ok": False, "stream": None, "issues": [_issue("error", "base_pdf_or_page_size_required", "pdf_overlay 必須指定 base_pdf 或 page_size")]}

    from pypdf import PdfWriter

    page_count = _max_template_page(template)
    if page_count > PDF_MAX_PAGE_GUARD:
        return {"ok": False, "stream": None, "issues": [_issue("error", "pdf_overlay_page_guard", f"page 數過大：{page_count}")]}
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=size[0], height=size[1])
    buffer = BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return {"ok": True, "stream": buffer, "path": ""}


def _copy_base_page(reader, page_number: int):
    page = copy.deepcopy(reader.pages[page_number - 1])
    _apply_rotation_to_page(page)
    return page


def _apply_rotation_to_page(page) -> None:
    try:
        if int(page.get("/Rotate", 0) or 0) % 360:
            page.transfer_rotation_to_content()
    except Exception:
        pass


def _page_geometry(page) -> dict[str, float]:
    media = page.mediabox
    crop = page.cropbox
    media_left = float(media.left)
    media_bottom = float(media.bottom)
    media_width = float(media.width)
    media_height = float(media.height)
    crop_left = float(crop.left) - media_left
    crop_bottom = float(crop.bottom) - media_bottom
    return {
        "media_width": media_width,
        "media_height": media_height,
        "crop_left": crop_left,
        "crop_bottom": crop_bottom,
        "crop_width": float(crop.width),
        "crop_height": float(crop.height),
    }


def _rect_to_points(mapping: dict[str, Any], geometry: dict[str, float]) -> dict[str, float]:
    x, y, width, height = [float(item) for item in mapping.get("rect_norm", [0, 0, 1, 1])]
    left = geometry["crop_left"] + x * geometry["crop_width"]
    rect_width = width * geometry["crop_width"]
    rect_height = height * geometry["crop_height"]
    top = geometry["crop_bottom"] + geometry["crop_height"] - y * geometry["crop_height"]
    return {
        "left": left,
        "bottom": top - rect_height,
        "width": rect_width,
        "height": rect_height,
    }


def _group_fields_by_page(template: dict[str, Any]) -> dict[int, list[tuple[int, dict[str, Any]]]]:
    grouped: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for idx, mapping in enumerate(template.get("fields", []) or [], start=1):
        if not isinstance(mapping, dict):
            continue
        page = _positive_int(mapping.get("page"))
        grouped.setdefault(page, []).append((idx, mapping))
    return grouped


def _max_template_page(template: dict[str, Any]) -> int:
    pages = [_positive_int(mapping.get("page")) for mapping in template.get("fields", []) or [] if isinstance(mapping, dict)]
    return max([1] + pages)


def _page_size(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        width = float(value[0])
        height = float(value[1])
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _font_name(preferred: str) -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    candidates = [preferred, "Helvetica", "STSong-Light"]
    for name in candidates:
        if not name:
            continue
        try:
            pdfmetrics.getFont(name)
            return name
        except KeyError:
            try:
                pdfmetrics.registerFont(UnicodeCIDFont(name))
                return name
            except Exception:
                continue
    return "Helvetica"


def _has_non_ascii(text: str) -> bool:
    return any(ord(char) > 127 for char in str(text or ""))


def _wrap_text(text: str, width: float, font: str, size: float) -> list[str]:
    from reportlab.pdfbase import pdfmetrics

    text = str(text or "")
    if not text:
        return [""]
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        current = ""
        for char in raw_line:
            candidate = current + char
            if current and pdfmetrics.stringWidth(candidate, font, size) > width:
                lines.append(current)
                current = char
            else:
                current = candidate
        lines.append(current)
    return lines or [""]


def _ellipsize(text: str, width: float, font: str, size: float) -> str:
    from reportlab.pdfbase import pdfmetrics

    text = str(text or "")
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    ellipsis = "..."
    while text and pdfmetrics.stringWidth(text + ellipsis, font, size) > width:
        text = text[:-1]
    return text + ellipsis if text else ellipsis


def _lines_height(lines: list[str], size: float) -> float:
    return len(lines) * size * 1.2


def _image_path(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("path", "") or "").strip()
    return str(value or "").strip()


def _image_scale(image_width: float, image_height: float, box_width: float, box_height: float, *, cover: bool) -> float:
    if image_width <= 0 or image_height <= 0:
        return 1.0
    scales = (box_width / image_width, box_height / image_height)
    return max(scales) if cover else min(scales)


def _column_widths(columns: list[Any], total_width: float) -> list[float]:
    explicit = []
    for col in columns:
        if isinstance(col, dict):
            explicit.append(_positive_float(col.get("width_norm")))
        else:
            explicit.append(0.0)
    if any(width > 0 for width in explicit):
        return [(width if width > 0 else 1 / len(columns)) * total_width for width in explicit]
    return [total_width / len(columns) for _ in columns]


def _column_source(column: Any) -> str:
    if isinstance(column, str):
        return column.strip()
    if isinstance(column, dict):
        return str(column.get("source", "") or "").strip()
    return ""


def _column_header(column: Any) -> str:
    if isinstance(column, str):
        return column.strip()
    if isinstance(column, dict):
        return str(column.get("header") or column.get("source") or "").strip()
    return ""


def _column_cell_type(column: Any) -> str:
    if isinstance(column, dict):
        return str(column.get("cell_type") or column.get("type") or "text").strip()
    return "text"


def _column_fit(column: Any) -> str:
    if isinstance(column, dict):
        return str(column.get("fit") or "contain").strip()
    return "contain"


def _table_column_issue_source(mapping: dict[str, Any], column_source: str) -> str:
    source = str(mapping.get("source", "") or "").strip()
    if not source or not column_source:
        return source or column_source
    if column_source.startswith(source):
        return column_source
    if source.endswith("[*]") or source.endswith("[0..n]"):
        return f"{source}.{column_source}"
    return f"{source}[*].{column_source}"


def _cell_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    if isinstance(value, dict):
        return str(value)
    return str(value)


def _draw_debug_rect(c, rect: dict[str, float]) -> None:
    c.saveState()
    c.setStrokeColorRGB(1, 0, 0)
    c.setLineWidth(0.8)
    c.rect(rect["left"], rect["bottom"], rect["width"], rect["height"], stroke=1, fill=0)
    c.restoreState()


def _draw_placeholder(c, rect: dict[str, float], label: str) -> None:
    c.saveState()
    c.setStrokeColorRGB(0.80, 0.20, 0.20)
    c.setFillColorRGB(0.98, 0.90, 0.90)
    c.rect(rect["left"], rect["bottom"], rect["width"], rect["height"], stroke=1, fill=1)
    c.setFillColorRGB(0.40, 0.05, 0.05)
    c.setFont("Helvetica", 8)
    c.drawString(rect["left"] + 4, rect["bottom"] + rect["height"] / 2, label)
    c.restoreState()


def _inset_rect(rect: dict[str, float], inset: float) -> dict[str, float]:
    inset = min(max(0.0, inset), rect["width"] / 2, rect["height"] / 2)
    return {
        "left": rect["left"] + inset,
        "bottom": rect["bottom"] + inset,
        "width": max(1.0, rect["width"] - inset * 2),
        "height": max(1.0, rect["height"] - inset * 2),
    }


def _validate_pdf(path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader

        pages = len(PdfReader(str(path)).pages)
    except Exception as exc:
        return {
            "ok": False,
            "pages": 0,
            "issue": _issue("error", "pdf_validation_failed", f"PDF 輸出後無法讀取：{exc}"),
        }
    if pages <= 0:
        return {
            "ok": False,
            "pages": 0,
            "issue": _issue("error", "pdf_has_no_pages", "PDF 輸出後沒有頁面"),
        }
    return {"ok": True, "pages": pages}


def _dependency_failure(name: str, exc: Exception) -> dict[str, Any]:
    return attach_output_envelope({
        "ok": False,
        "path": "",
        "summary": _empty_summary(),
        "issues": [_issue("error", "renderer_dependency_missing", f"缺少 {name}：{exc}")],
    })


def _field_issue(severity: str, code: str, mapping: dict[str, Any], message: str) -> dict[str, Any]:
    issue = _issue(severity, code, message)
    issue["source"] = str(mapping.get("source", "") or "")
    field_index = _positive_int(mapping.get("_field_index"))
    if field_index:
        issue["field_index"] = field_index
    return issue


def _issue(severity: str, code: str, message: str) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message}


def _empty_summary() -> dict[str, int]:
    return {"text": 0, "image": 0, "table": 0, "rows": 0}


def _add_summary(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = int(target.get(key, 0)) + int(value or 0)


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
