# -*- coding: utf-8 -*-
"""Shared runner for CanonicalReport-based site output bundles."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from canonical_report import collect_canonical_report_set
from pdf_overlay_renderer import render_pdf_overlay_for_report
from site_statistics_exporter import export_site_statistics_workbook


TemplateBuilder = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class SiteOutputBundleConfig:
    marker_file: str
    marker_text: str
    result_root_key: str
    exists_error_message: str
    overwrite_refusal_message: str
    report_set_filename: str
    statistics_filename: str
    summary_template_filename: str
    photo_grid_template_filename: str
    base_pdf_filename: str
    summary_filename: str
    summary_template_file_key: str
    photo_grid_template_file_key: str
    summary_pdf_prefix: str
    photo_grid_pdf_prefix: str
    summary_template_builder: TemplateBuilder
    photo_grid_template_builder: TemplateBuilder


def run_site_output_bundle(
    output_dir: str | os.PathLike[str],
    *,
    config: SiteOutputBundleConfig,
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
    render_summary_pdf = bool(render_pdf and render_summary_pdf)
    render_photo_grid_pdf = bool(render_pdf and render_photo_grid_pdf)
    render_statistics = bool(render_statistics)
    if not (render_statistics or render_summary_pdf or render_photo_grid_pdf):
        raise ValueError("至少要選擇一種輸出內容")

    project = Path(project_root or Path.cwd()).resolve()
    attachments = Path(attachments_root or project / "attachments").resolve()
    root = Path(output_dir).resolve()
    _prepare_output_root(root, config=config, overwrite=overwrite)

    records_dir = root / "records"
    output_dir_path = root / "output"
    template_dir = root / "templates"
    records_dir.mkdir(parents=True, exist_ok=True)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    template_dir.mkdir(parents=True, exist_ok=True)

    report_set = collect_canonical_report_set(
        project_root=project,
        attachments_root=attachments,
        store={"records": [], "details": [], "materials": []},
        include_report_keys=include_report_keys,
    )
    report_set_path = records_dir / config.report_set_filename
    statistics_path = output_dir_path / config.statistics_filename
    summary_template_path = template_dir / config.summary_template_filename
    photo_grid_template_path = template_dir / config.photo_grid_template_filename
    base_pdf_path = template_dir / config.base_pdf_filename
    summary_path = root / config.summary_filename

    _write_json(report_set_path, report_set)
    statistics_result = export_site_statistics_workbook(str(statistics_path), report_set=report_set) if render_statistics else ""
    summary_template = config.summary_template_builder()
    photo_grid_template = config.photo_grid_template_builder()
    _write_json(summary_template_path, summary_template)
    _write_json(photo_grid_template_path, photo_grid_template)
    _write_blank_base_pdf(base_pdf_path)

    renders = []
    if render_summary_pdf or render_photo_grid_pdf:
        for report in report_set.get("reports", []) or []:
            folder = str(report.get("report", {}).get("folder", "") or "report")
            safe_folder = _safe_filename(folder)
            if render_summary_pdf:
                renders.append(_render_output_pdf(
                    report,
                    summary_template,
                    output_dir_path / f"{config.summary_pdf_prefix}_{safe_folder}.pdf",
                    template_dir=template_dir,
                    render_png=render_png,
                    folder=folder,
                    template_name="summary",
                ))
            if render_photo_grid_pdf:
                renders.append(_render_output_pdf(
                    report,
                    photo_grid_template,
                    output_dir_path / f"{config.photo_grid_pdf_prefix}_{safe_folder}.pdf",
                    template_dir=template_dir,
                    render_png=render_png,
                    folder=folder,
                    template_name="photo_grid",
                ))

    statistics_ok = (not render_statistics) or bool(Path(statistics_result).exists())
    pdf_ok = (not (render_summary_pdf or render_photo_grid_pdf)) or all(item.get("ok") for item in renders)
    ok = statistics_ok and pdf_ok
    files = {
        "report_set": str(report_set_path),
        "statistics_xlsx": str(statistics_path) if render_statistics else "",
        config.summary_template_file_key: str(summary_template_path),
        config.photo_grid_template_file_key: str(photo_grid_template_path),
        "pdf_base": str(base_pdf_path),
        "summary": str(summary_path),
    }
    summary = {
        "ok": ok,
        "project": str(project),
        "attachments_root": str(attachments),
        config.result_root_key: str(root),
        "scope": {
            "mode": "filtered" if include_report_keys is not None else "all",
            "requested_count": len(include_report_keys or []),
        },
        "content": {
            "statistics_xlsx": render_statistics,
            "summary_pdf": render_summary_pdf,
            "photo_grid_pdf": render_photo_grid_pdf,
            "png": bool(render_png),
        },
        "report_count": len(report_set.get("reports", []) or []),
        "files": files,
        "renders": renders,
        "aggregates": report_set.get("aggregates", {}),
        "issues": report_set.get("issues", []),
    }
    _write_json(summary_path, summary)
    return summary


def _render_output_pdf(
    report: dict[str, Any],
    template: dict[str, Any],
    output_pdf: Path,
    *,
    template_dir: Path,
    render_png: bool,
    folder: str,
    template_name: str,
) -> dict[str, Any]:
    result = render_pdf_overlay_for_report(report, template, output_pdf, template_dir=template_dir)
    png_paths = _render_pdf_pngs(output_pdf) if render_png and result.get("ok") else []
    return {
        "folder": folder,
        "template": template_name,
        "ok": bool(result.get("ok")),
        "path": result.get("path", ""),
        "pages": result.get("pdf_validation", {}).get("pages", 0),
        "summary": result.get("summary", {}),
        "issue_codes": [
            issue.get("code", "")
            for issue in result.get("issues", []) or []
            if issue.get("severity") != "info"
        ],
        "pngs": png_paths,
    }


def _prepare_output_root(root: Path, *, config: SiteOutputBundleConfig, overwrite: bool) -> None:
    if root.exists():
        marker = root / config.marker_file
        if not overwrite:
            raise FileExistsError(f"{config.exists_error_message}{root}")
        if not marker.exists():
            raise RuntimeError(f"{config.overwrite_refusal_message}{root}")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / config.marker_file).write_text(config.marker_text, encoding="utf-8")


def _write_blank_base_pdf(path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595.32, height=841.92)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        writer.write(f)


def _render_pdf_pngs(pdf_path: Path) -> list[str]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return []
    prefix = pdf_path.with_suffix("")
    result = subprocess.run(
        [pdftoppm, "-png", str(pdf_path), str(prefix)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [str(path) for path in sorted(pdf_path.parent.glob(f"{prefix.name}-*.png"))]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _safe_filename(value: str) -> str:
    text = str(value or "").strip() or "report"
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in text)
