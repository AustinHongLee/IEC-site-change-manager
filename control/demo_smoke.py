# -*- coding: utf-8 -*-
"""Create a repeatable demo project and render smoke outputs."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from canonical_report import collect_canonical_report_set
from output_capabilities import build_output_capability_report
from renderer_registry import render_with_template
from site_statistics_exporter import export_site_statistics_workbook
from template_dry_run import dry_run_template_for_report
from template_mapping import validate_template_mapping
from workbook_pdf_converter import convert_workbook_to_pdf


DEMO_MARKER = ".iec_demo_project"
DEMO_DATE = "20260617"
DEMO_FOLDER = "0547_AG"
EDGE_CASES = {
    "0547_AG": [],
    "0601_NO_AFTER": ["missing_image_value"],
    "0602_MATERIAL_OVERFLOW": ["table_overflow"],
    "0603_MANY_PHOTOS": ["table_overflow"],
    "0604_MULTI_PAGE_PDF": [],
}


def run_demo_output_smoke(
    output_dir: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    attempt_pdf: bool = False,
    require_pdf: bool = False,
) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    _prepare_demo_root(root, overwrite=overwrite)
    _write_demo_attachments(root)

    records_dir = root / "records"
    output_dir_path = root / "output"
    template_dir = root / "templates"
    records_dir.mkdir(parents=True, exist_ok=True)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    template_dir.mkdir(parents=True, exist_ok=True)

    report_set = collect_canonical_report_set(
        project_root=root,
        attachments_root=root / "attachments",
        store={"records": [], "details": [], "materials": []},
    )
    template = build_demo_xlsx_template()
    pdf_overlay_template = build_demo_pdf_overlay_template()

    report_set_path = records_dir / "demo_canonical_report_set.json"
    template_path = template_dir / "demo_field_report.template.json"
    pdf_overlay_template_path = template_dir / "demo_pdf_overlay.template.json"
    pdf_overlay_base_path = template_dir / "vendor_form.pdf"
    rendered_xlsx = output_dir_path / "demo_field_report.xlsx"
    site_statistics_xlsx = output_dir_path / "demo_site_statistics.xlsx"
    rendered_pdf = output_dir_path / "demo_field_report.pdf"

    _write_json(report_set_path, report_set)
    _write_json(template_path, template)
    _write_json(pdf_overlay_template_path, pdf_overlay_template)
    _write_demo_base_pdf(pdf_overlay_base_path)
    report = report_set["reports"][0] if report_set.get("reports") else {}
    template_result = render_with_template(report, template, str(rendered_xlsx), template_dir=str(template_dir))
    pdf_overlay_validation = validate_template_mapping(pdf_overlay_template)
    site_statistics_path = export_site_statistics_workbook(str(site_statistics_xlsx), report_set=report_set)

    pdf_result = None
    if attempt_pdf:
        pdf_result = convert_workbook_to_pdf(rendered_xlsx, rendered_pdf)

    issues = []
    if not template_result.get("ok"):
        issues.extend(template_result.get("issues", []))
    if not pdf_overlay_validation.get("ok"):
        issues.extend(
            {"severity": "error", "code": "pdf_overlay_template_invalid", "message": error}
            for error in pdf_overlay_validation.get("errors", [])
        )
    if attempt_pdf and require_pdf and not (pdf_result or {}).get("ok"):
        issues.extend((pdf_result or {}).get("issues", []))

    ok = (
        bool(template_result.get("ok"))
        and bool(pdf_overlay_validation.get("ok"))
        and (not require_pdf or bool((pdf_result or {}).get("ok")))
    )
    return {
        "ok": ok,
        "project": str(root),
        "report_count": len(report_set.get("reports", []) or []),
        "files": {
            "report_set": str(report_set_path),
            "template": str(template_path),
            "pdf_overlay_template": str(pdf_overlay_template_path),
            "pdf_overlay_base": str(pdf_overlay_base_path),
            "rendered_xlsx": str(rendered_xlsx) if rendered_xlsx.exists() else "",
            "site_statistics_xlsx": str(site_statistics_path) if Path(site_statistics_path).exists() else "",
            "rendered_pdf": str(rendered_pdf) if rendered_pdf.exists() else "",
        },
        "capabilities": build_output_capability_report(),
        "xlsx_template": template_result,
        "pdf_overlay_template": pdf_overlay_validation,
        "pdf_conversion": pdf_result,
        "issues": issues,
    }


def run_demo_edge_matrix(
    output_dir: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    _prepare_demo_root(root, overwrite=overwrite)
    _write_edge_attachments(root)

    records_dir = root / "records"
    template_dir = root / "templates"
    records_dir.mkdir(parents=True, exist_ok=True)
    template_dir.mkdir(parents=True, exist_ok=True)

    report_set = collect_canonical_report_set(
        project_root=root,
        attachments_root=root / "attachments",
        store={"records": [], "details": [], "materials": []},
    )
    template = build_demo_edge_matrix_template()
    pdf_overlay_template = build_demo_pdf_overlay_template()

    report_set_path = records_dir / "edge_canonical_report_set.json"
    template_path = template_dir / "edge_matrix.template.json"
    pdf_overlay_template_path = template_dir / "edge_pdf_overlay.template.json"
    pdf_overlay_base_path = template_dir / "vendor_form.pdf"
    pdf_overlay_rotated_template_path = template_dir / "edge_pdf_overlay_rotated.template.json"
    pdf_overlay_rotated_base_path = template_dir / "rotated_vendor_form.pdf"
    _write_json(report_set_path, report_set)
    _write_json(template_path, template)
    _write_json(pdf_overlay_template_path, pdf_overlay_template)
    _write_json(pdf_overlay_rotated_template_path, build_demo_pdf_overlay_template(base_pdf="rotated_vendor_form.pdf"))
    _write_demo_base_pdf(pdf_overlay_base_path)
    _write_demo_base_pdf(pdf_overlay_rotated_base_path, rotate=90)

    validation = validate_template_mapping(template)
    pdf_overlay_validation = validate_template_mapping(pdf_overlay_template)
    cases = []
    for report in report_set.get("reports", []) or []:
        folder = report.get("report", {}).get("folder", "")
        dry_run = dry_run_template_for_report(report, template)
        issue_codes = [issue.get("code", "") for issue in dry_run.get("issues", [])]
        expected_codes = EDGE_CASES.get(folder, [])
        expectation_ok = all(code in issue_codes for code in expected_codes)
        cases.append({
            "folder": folder,
            "dry_run_ok": dry_run.get("ok"),
            "issue_codes": issue_codes,
            "expected_issue_codes": expected_codes,
            "expectation_ok": expectation_ok,
            "attachment_pdf_pages": report.get("attachment_pdf", {}).get("pages", ""),
        })

    known_folders = set(EDGE_CASES)
    found_folders = {case["folder"] for case in cases}
    missing_cases = sorted(known_folders - found_folders)
    ok = (
        validation.get("ok")
        and pdf_overlay_validation.get("ok")
        and not missing_cases
        and all(case["expectation_ok"] for case in cases if case["folder"] in known_folders)
        and _multi_page_case_ok(cases)
    )
    return {
        "ok": bool(ok),
        "project": str(root),
        "report_count": len(report_set.get("reports", []) or []),
        "files": {
            "report_set": str(report_set_path),
            "template": str(template_path),
            "pdf_overlay_template": str(pdf_overlay_template_path),
            "pdf_overlay_base": str(pdf_overlay_base_path),
            "pdf_overlay_rotated_template": str(pdf_overlay_rotated_template_path),
            "pdf_overlay_rotated_base": str(pdf_overlay_rotated_base_path),
        },
        "validation": validation,
        "pdf_overlay_template": pdf_overlay_validation,
        "cases": cases,
        "missing_cases": missing_cases,
        "issues": _edge_matrix_issues(validation, pdf_overlay_validation, cases, missing_cases),
    }


def build_demo_xlsx_template() -> dict[str, Any]:
    return {
        "template_id": "demo_field_report",
        "schema_version": "template_mapping.v1",
        "kind": "xlsx_template",
        "sheet": "現場修改單",
        "fields": [
            {"type": "text", "source": "report.folder", "cell": "A1"},
            {"type": "text", "source": "report.date", "cell": "B1"},
            {"type": "text", "source": "report.series", "cell": "C1"},
            {"type": "text", "source": "report.description", "cell": "A3"},
            {"type": "text", "source": "welds.summary", "cell": "A5"},
            {"type": "text", "source": "materials.summary", "cell": "A6"},
            {
                "type": "image",
                "source": "photos.before[0].path",
                "anchor": "A8",
                "max_width_px": 240,
                "max_height_px": 160,
                "size_cells": [3, 8],
            },
            {
                "type": "image",
                "source": "photos.after[0].path",
                "anchor": "E8",
                "max_width_px": 240,
                "max_height_px": 160,
                "size_cells": [3, 8],
            },
            {
                "type": "table",
                "source": "welds.rows",
                "start_cell": "A18",
                "max_rows": 10,
                "write_header": True,
                "columns": [
                    {"source": "code", "header": "焊口"},
                    {"source": "size", "header": "尺寸"},
                    {"source": "mark", "header": "標記"},
                ],
            },
            {
                "type": "table",
                "source": "materials.rows",
                "start_cell": "E18",
                "max_rows": 10,
                "write_header": True,
                "columns": [
                    {"source": "component", "header": "零件"},
                    {"source": "size", "header": "尺寸"},
                    {"source": "sch", "header": "SCH"},
                    {"source": "qty", "header": "數量"},
                    {"source": "unit", "header": "單位"},
                ],
            },
        ],
    }


def build_demo_edge_matrix_template() -> dict[str, Any]:
    return {
        "template_id": "demo_edge_matrix",
        "schema_version": "template_mapping.v1",
        "kind": "xlsx_template",
        "fields": [
            {"type": "text", "source": "report.folder", "cell": "A1"},
            {"type": "text", "source": "attachment_pdf.name", "cell": "A2"},
            {"type": "image", "source": "photos.before[0].path", "anchor": "A4"},
            {"type": "image", "source": "photos.after[0].path", "anchor": "D4"},
            {
                "type": "table",
                "source": "materials.rows",
                "start_cell": "A12",
                "max_rows": 2,
                "columns": ["component", "size", "sch", "qty", "unit"],
            },
            {
                "type": "table",
                "source": "photos.before[*]",
                "start_cell": "A18",
                "max_rows": 2,
                "columns": ["name", "path"],
            },
        ],
    }


def build_demo_pdf_overlay_template(*, base_pdf: str = "vendor_form.pdf") -> dict[str, Any]:
    return {
        "template_id": "demo_pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "kind": "pdf_overlay",
        "base_pdf": base_pdf,
        "coordinate_space": "normalized",
        "fields": [
            {
                "type": "text",
                "source": "report.folder",
                "page": 1,
                "rect_norm": [0.08, 0.08, 0.28, 0.04],
                "font_size": 10,
                "overflow": "shrink",
            },
            {
                "type": "text",
                "source": "welds.summary",
                "page": 1,
                "rect_norm": [0.08, 0.14, 0.55, 0.05],
                "font_size": 10,
                "overflow": "wrap",
            },
            {
                "type": "image",
                "source": "photos.before[0].path",
                "page": 1,
                "rect_norm": [0.08, 0.24, 0.38, 0.28],
                "fit": "contain",
            },
            {
                "type": "image",
                "source": "photos.after[0].path",
                "page": 1,
                "rect_norm": [0.54, 0.24, 0.38, 0.28],
                "fit": "contain",
            },
            {
                "type": "table",
                "source": "materials.rows",
                "page": 1,
                "rect_norm": [0.08, 0.60, 0.84, 0.25],
                "rows_per_page": 8,
                "overflow": "new_page",
                "columns": [
                    {"source": "component", "header": "零件", "width_norm": 0.34},
                    {"source": "size", "header": "尺寸", "width_norm": 0.18},
                    {"source": "sch", "header": "SCH", "width_norm": 0.18},
                    {"source": "qty", "header": "數量", "width_norm": 0.15},
                    {"source": "unit", "header": "單位", "width_norm": 0.15},
                ],
            },
        ],
    }


def _prepare_demo_root(root: Path, *, overwrite: bool) -> None:
    if root.exists():
        marker = root / DEMO_MARKER
        if not overwrite:
            raise FileExistsError(f"demo output 已存在，若要重建請加 overwrite：{root}")
        if not marker.exists():
            raise RuntimeError(f"拒絕覆寫非 demo 資料夾：{root}")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / DEMO_MARKER).write_text("generated demo project\n", encoding="utf-8")


def _write_demo_attachments(root: Path) -> None:
    folder = root / "attachments" / DEMO_DATE / DEMO_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "GroupWeld.txt").write_text("1r2\n2r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("現場加長修改，含兩口焊口與一組 before/after 照片", encoding="utf-8")
    (folder / "materials.txt").write_text(
        "Pipe (管),2\",SCH 40,SS,3 M,測試管材\n"
        "Elbow (彎頭),2\",SCH 40,SS,1 個,測試彎頭\n",
        encoding="utf-8",
    )
    _write_demo_image(folder / "before_1.png", "BEFORE", (196, 54, 48))
    _write_demo_image(folder / "after_1.png", "AFTER", (39, 128, 82))
    _write_demo_pdf(folder / "0547.DW-demo.pdf")


def _write_edge_attachments(root: Path) -> None:
    _write_demo_attachments(root)
    _write_edge_case_no_after(root)
    _write_edge_case_material_overflow(root)
    _write_edge_case_many_photos(root)
    _write_edge_case_multi_page_pdf(root)


def _write_edge_case_no_after(root: Path) -> None:
    folder = root / "attachments" / "20260618" / "0601_NO_AFTER"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "GroupWeld.txt").write_text("1r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("缺 after 照片 edge case", encoding="utf-8")
    (folder / "materials.txt").write_text("Pipe (管),2\",SCH 40,SS,1 M,缺照片測試\n", encoding="utf-8")
    _write_demo_image(folder / "before_1.png", "ONLY BEFORE", (59, 130, 246))
    _write_demo_pdf(folder / "0601.DW-demo.pdf")


def _write_edge_case_material_overflow(root: Path) -> None:
    folder = root / "attachments" / "20260619" / "0602_MATERIAL_OVERFLOW"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "GroupWeld.txt").write_text("1r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("材料列超過模板預留列數 edge case", encoding="utf-8")
    (folder / "materials.txt").write_text(
        "Pipe (管),2\",SCH 40,SS,1 M,overflow 1\n"
        "Elbow (彎頭),2\",SCH 40,SS,1 個,overflow 2\n"
        "Tee (三通),2\",SCH 40,SS,1 個,overflow 3\n"
        "Flange (法蘭),2\",SCH 40,SS,2 個,overflow 4\n",
        encoding="utf-8",
    )
    _write_demo_image(folder / "before_1.png", "BEFORE", (196, 54, 48))
    _write_demo_image(folder / "after_1.png", "AFTER", (39, 128, 82))
    _write_demo_pdf(folder / "0602.DW-demo.pdf")


def _write_edge_case_many_photos(root: Path) -> None:
    folder = root / "attachments" / "20260620" / "0603_MANY_PHOTOS"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "GroupWeld.txt").write_text("1r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("before 照片數超過模板預留列數 edge case", encoding="utf-8")
    (folder / "materials.txt").write_text("Pipe (管),2\",SCH 40,SS,1 M,多照片測試\n", encoding="utf-8")
    for idx in range(1, 5):
        _write_demo_image(folder / f"before_{idx}.png", f"BEFORE {idx}", (180, 83, 9))
    _write_demo_image(folder / "after_1.png", "AFTER", (39, 128, 82))
    _write_demo_pdf(folder / "0603.DW-demo.pdf")


def _write_edge_case_multi_page_pdf(root: Path) -> None:
    folder = root / "attachments" / "20260621" / "0604_MULTI_PAGE_PDF"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "GroupWeld.txt").write_text("1r2\n", encoding="utf-8")
    (folder / "note.txt").write_text("附件 PDF 多頁 edge case", encoding="utf-8")
    (folder / "materials.txt").write_text("Pipe (管),2\",SCH 40,SS,1 M,多頁 PDF 測試\n", encoding="utf-8")
    _write_demo_image(folder / "before_1.png", "BEFORE", (196, 54, 48))
    _write_demo_image(folder / "after_1.png", "AFTER", (39, 128, 82))
    _write_demo_pdf(folder / "0604.DW-demo.pdf", pages=2)


def _write_demo_image(path: Path, label: str, color: tuple[int, int, int]) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (360, 240), (245, 247, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 336, 216), outline=color, width=6)
    draw.text((52, 96), label, fill=color)
    draw.text((52, 126), "IEC field demo", fill=(40, 48, 60))
    image.save(path)


def _write_demo_pdf(path: Path, *, pages: int = 1) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(max(1, pages)):
        writer.add_blank_page(width=360, height=240)
    with open(path, "wb") as f:
        writer.write(f)


def _write_demo_base_pdf(path: Path, *, rotate: int = 0) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    page = writer.add_blank_page(width=595.32, height=841.92)
    if rotate:
        page.rotate(rotate)
    with open(path, "wb") as f:
        writer.write(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _multi_page_case_ok(cases: list[dict[str, Any]]) -> bool:
    for case in cases:
        if case.get("folder") == "0604_MULTI_PAGE_PDF":
            return case.get("attachment_pdf_pages") == 2
    return False


def _edge_matrix_issues(
    validation: dict[str, Any],
    pdf_overlay_validation: dict[str, Any],
    cases: list[dict[str, Any]],
    missing_cases: list[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for error in validation.get("errors", []):
        issues.append({"severity": "error", "code": "edge_template_invalid", "message": error})
    for error in pdf_overlay_validation.get("errors", []):
        issues.append({"severity": "error", "code": "edge_pdf_overlay_invalid", "message": error})
    for folder in missing_cases:
        issues.append({"severity": "error", "code": "edge_case_missing", "message": f"edge case 未建立：{folder}"})
    for case in cases:
        if not case.get("expectation_ok"):
            issues.append({
                "severity": "error",
                "code": "edge_expectation_missing",
                "message": f"{case.get('folder')} 未抓到預期 issue：{case.get('expected_issue_codes')}",
            })
    if not _multi_page_case_ok(cases):
        issues.append({
            "severity": "error",
            "code": "edge_multi_page_pdf_missing",
            "message": "0604_MULTI_PAGE_PDF 未被辨識為 2 頁 PDF",
        })
    return issues
