# -*- coding: utf-8 -*-
"""Formal site output center for CanonicalReport-based project outputs."""

from __future__ import annotations

import os
from typing import Any

from site_output_runner import SiteOutputBundleConfig, run_site_output_bundle


OUTPUT_CENTER_MARKER = ".iec_site_output_center"


def run_site_output_center(
    output_dir: str | os.PathLike[str],
    *,
    project_root: str | os.PathLike[str] | None = None,
    attachments_root: str | os.PathLike[str] | None = None,
    include_report_keys: list[tuple[str, str]] | None = None,
    overwrite: bool = False,
    render_pdf: bool = True,
    render_png: bool = False,
    render_statistics: bool = True,
    render_summary_pdf: bool = True,
    render_photo_grid_pdf: bool = True,
) -> dict[str, Any]:
    return run_site_output_bundle(
        output_dir,
        config=_site_output_config(),
        project_root=project_root,
        attachments_root=attachments_root,
        include_report_keys=include_report_keys,
        overwrite=overwrite,
        render_pdf=render_pdf,
        render_png=render_png,
        render_statistics=render_statistics,
        render_summary_pdf=render_summary_pdf,
        render_photo_grid_pdf=render_photo_grid_pdf,
    )


def build_site_summary_pdf_template() -> dict[str, Any]:
    return {
        "template_id": "site_summary_pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "kind": "pdf_overlay",
        "base_pdf": "site_output_base.pdf",
        "coordinate_space": "normalized",
        "fields": [
            {"type": "text", "source": "report.folder", "page": 1, "rect_norm": [0.08, 0.06, 0.24, 0.035], "font_size": 12, "overflow": "shrink"},
            {"type": "text", "source": "report.date", "page": 1, "rect_norm": [0.36, 0.06, 0.24, 0.035], "font_size": 10, "overflow": "shrink"},
            {"type": "text", "source": "welds.summary", "page": 1, "rect_norm": [0.08, 0.105, 0.84, 0.05], "font_size": 10, "overflow": "wrap"},
            {"type": "text", "source": "report.description", "page": 1, "rect_norm": [0.08, 0.165, 0.84, 0.10], "font_size": 9, "overflow": "wrap"},
            {"type": "image", "source": "photos.before[0].path", "page": 1, "rect_norm": [0.08, 0.30, 0.38, 0.24], "fit": "contain"},
            {"type": "image", "source": "photos.after[0].path", "page": 1, "rect_norm": [0.54, 0.30, 0.38, 0.24], "fit": "contain"},
            {
                "type": "table",
                "source": "materials.rows",
                "page": 1,
                "rect_norm": [0.08, 0.60, 0.84, 0.20],
                "rows_per_page": 2,
                "overflow": "new_page",
                "columns": [
                    {"source": "component", "header": "零件", "width_norm": 0.34},
                    {"source": "size", "header": "尺寸", "width_norm": 0.18},
                    {"source": "material", "header": "材質", "width_norm": 0.18},
                    {"source": "qty", "header": "數量", "width_norm": 0.15},
                    {"source": "unit", "header": "單位", "width_norm": 0.15},
                ],
            },
        ],
    }


def build_site_photo_grid_pdf_template() -> dict[str, Any]:
    return {
        "template_id": "site_photo_grid_pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "kind": "pdf_overlay",
        "base_pdf": "site_output_base.pdf",
        "coordinate_space": "normalized",
        "fields": [
            {"type": "text", "source": "report.folder", "page": 1, "rect_norm": [0.06, 0.04, 0.30, 0.035], "font_size": 12, "overflow": "shrink"},
            {"type": "text", "source": "photos.mode", "page": 1, "rect_norm": [0.40, 0.04, 0.18, 0.035], "font_size": 10, "overflow": "shrink"},
            {
                "type": "table",
                "source": "photos.before[*]",
                "page": 1,
                "rect_norm": [0.06, 0.10, 0.88, 0.36],
                "rows_per_page": 2,
                "row_height_pt": 90,
                "header_height_pt": 18,
                "overflow": "new_page",
                "columns": [
                    {"source": "path", "header": "Before", "cell_type": "image", "fit": "contain", "width_norm": 0.68},
                    {"source": "name", "header": "檔名", "width_norm": 0.32},
                ],
            },
            {
                "type": "table",
                "source": "photos.after[*]",
                "page": 1,
                "rect_norm": [0.06, 0.54, 0.88, 0.36],
                "rows_per_page": 2,
                "row_height_pt": 90,
                "header_height_pt": 18,
                "overflow": "new_page",
                "columns": [
                    {"source": "path", "header": "After", "cell_type": "image", "fit": "contain", "width_norm": 0.68},
                    {"source": "name", "header": "檔名", "width_norm": 0.32},
                ],
            },
        ],
    }


def _site_output_config() -> SiteOutputBundleConfig:
    return SiteOutputBundleConfig(
        marker_file=OUTPUT_CENTER_MARKER,
        marker_text="generated site output center\n",
        result_root_key="output_center",
        exists_error_message="輸出中心資料夾已存在，若要重建請允許覆寫：",
        overwrite_refusal_message="拒絕覆寫非輸出中心資料夾：",
        report_set_filename="canonical_report_set.json",
        statistics_filename="site_statistics.xlsx",
        summary_template_filename="site_summary_pdf.template.json",
        photo_grid_template_filename="site_photo_grid.template.json",
        base_pdf_filename="site_output_base.pdf",
        summary_filename="output_center_summary.json",
        summary_template_file_key="summary_pdf_template",
        photo_grid_template_file_key="photo_grid_template",
        summary_pdf_prefix="site_summary",
        photo_grid_pdf_prefix="site_photo_grid",
        summary_template_builder=build_site_summary_pdf_template,
        photo_grid_template_builder=build_site_photo_grid_pdf_template,
    )
