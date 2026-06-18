# -*- coding: utf-8 -*-
"""Field-path catalog shared by CanonicalReport and template tooling."""

from __future__ import annotations


FIELD_PATH_CATALOG: tuple[str, ...] = (
    "report.report_id",
    "report.date",
    "report.series",
    "report.dwg_no",
    "report.line_number",
    "report.change_type",
    "report.description",
    "report.folder",
    "report.status",
    "report.fingerprint",
    "welds.summary",
    "welds.count",
    "welds.total_size",
    "welds.rows",
    "welds.rows[*].weld_no",
    "welds.rows[*].mark",
    "welds.rows[*].size",
    "welds.rows[*].material",
    "welds.rows[*].thickness",
    "welds.rows[*].code",
    "materials.summary",
    "materials.count",
    "materials.rows",
    "materials.rows[*].component",
    "materials.rows[*].size",
    "materials.rows[*].sch",
    "materials.rows[*].material",
    "materials.rows[*].qty",
    "materials.rows[*].unit",
    "materials.rows[*].category",
    "materials.rows[*].remark",
    "photos.before",
    "photos.before[*]",
    "photos.after",
    "photos.after[*]",
    "photos.before[*].name",
    "photos.before[*].path",
    "photos.before[*].w",
    "photos.before[*].h",
    "photos.after[*].name",
    "photos.after[*].path",
    "photos.after[*].w",
    "photos.after[*].h",
    "photos.mode",
    "attachment_pdf.path",
    "attachment_pdf.name",
    "note.raw",
    "completeness.level",
    "completeness.missing[*]",
)


def list_field_paths() -> list[str]:
    return list(FIELD_PATH_CATALOG)
