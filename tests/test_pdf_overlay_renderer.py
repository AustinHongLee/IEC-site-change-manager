# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import pdf_overlay_renderer
from pdf_overlay_renderer import render_pdf_overlay_for_report


def _write_base_pdf(path: Path, *, width: float = 400, height: float = 300) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    with open(path, "wb") as f:
        writer.write(f)


def _write_two_page_base_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=300)
    writer.add_blank_page(width=300, height=400)
    with open(path, "wb") as f:
        writer.write(f)


def _write_rotated_base_pdf(path: Path, *, width: float = 400, height: float = 300, rotate: int = 90) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=width, height=height)
    page.rotate(rotate)
    with open(path, "wb") as f:
        writer.write(f)


def _write_image(path: Path) -> None:
    Image.new("RGB", (80, 50), (220, 80, 60)).save(path)


def _report(image_path: Path):
    return {
        "report": {"report_id": "R-PDF", "description": "field overlay"},
        "photos": {"before": [{"path": str(image_path)}], "after": []},
        "materials": {"rows": [{"component": "Pipe", "qty": 2, "unit": "M"}]},
    }


def _template(base_pdf: str):
    return {
        "kind": "pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "base_pdf": base_pdf,
        "coordinate_space": "normalized",
        "debug": True,
        "fields": [
            {
                "type": "text",
                "source": "report.report_id",
                "page": 1,
                "rect_norm": [0.05, 0.06, 0.35, 0.08],
                "overflow": "shrink",
            },
            {
                "type": "image",
                "source": "photos.before[0].path",
                "page": 1,
                "rect_norm": [0.05, 0.18, 0.35, 0.30],
                "fit": "contain",
            },
            {
                "type": "table",
                "source": "materials.rows",
                "page": 1,
                "rect_norm": [0.05, 0.56, 0.60, 0.25],
                "rows_per_page": 4,
                "overflow": "new_page",
                "columns": [
                    {"source": "component", "header": "Item", "width_norm": 0.50},
                    {"source": "qty", "header": "Qty", "width_norm": 0.25},
                    {"source": "unit", "header": "Unit", "width_norm": 0.25},
                ],
            },
        ],
    }


def test_render_pdf_overlay_writes_text_image_table(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    image = tmp_path / "before.png"
    output = tmp_path / "out.pdf"
    _write_base_pdf(base_pdf)
    _write_image(image)

    result = render_pdf_overlay_for_report(_report(image), _template(str(base_pdf)), output, template_dir=tmp_path)

    assert result["ok"] is True
    assert result["result_schema_version"] == "output_result.v1"
    assert result["outputs"][0]["kind"] == "pdf_overlay"
    assert result["summary"]["text"] == 1
    assert result["summary"]["image"] == 1
    assert result["summary"]["table"] == 1
    assert output.exists()
    reader = PdfReader(str(output))
    assert len(reader.pages) == 1
    assert "R-PDF" in (reader.pages[0].extract_text() or "")


def test_render_pdf_overlay_reports_missing_base_pdf(tmp_path):
    image = tmp_path / "before.png"
    output = tmp_path / "out.pdf"
    _write_image(image)
    template = _template(str(tmp_path / "missing.pdf"))

    result = render_pdf_overlay_for_report(_report(image), template, output, template_dir=tmp_path)

    assert result["ok"] is False
    assert not output.exists()
    assert result["issues"][0]["code"] == "base_pdf_missing"


def test_render_pdf_overlay_rejects_text_overflow_error_without_output(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    image = tmp_path / "before.png"
    output = tmp_path / "text_overflow.pdf"
    _write_base_pdf(base_pdf)
    _write_image(image)
    report = _report(image)
    report["report"]["description"] = "very long field note " * 80
    template = {
        "kind": "pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "base_pdf": str(base_pdf),
        "coordinate_space": "normalized",
        "fields": [
            {
                "type": "text",
                "source": "report.description",
                "page": 1,
                "rect_norm": [0.05, 0.05, 0.16, 0.04],
                "font_size": 12,
                "overflow": "error",
            }
        ],
    }

    result = render_pdf_overlay_for_report(report, template, output, template_dir=tmp_path)

    assert result["ok"] is False
    assert result["path"] == ""
    assert not output.exists()
    overflow = next(issue for issue in result["issues"] if issue["code"] == "text_overflow")
    assert overflow["severity"] == "error"
    assert overflow["field_index"] == 1


def test_render_pdf_overlay_table_new_page_adds_continuation_pages(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    image = tmp_path / "before.png"
    output = tmp_path / "table_new_page.pdf"
    _write_base_pdf(base_pdf)
    _write_image(image)
    report = _report(image)
    report["materials"]["rows"] = [
        {"component": "Pipe", "qty": 2, "unit": "M"},
        {"component": "Elbow", "qty": 1, "unit": "EA"},
        {"component": "Tee", "qty": 3, "unit": "EA"},
    ]
    template = {
        "kind": "pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "base_pdf": str(base_pdf),
        "coordinate_space": "normalized",
        "fields": [
            {
                "type": "table",
                "source": "materials.rows",
                "page": 1,
                "rect_norm": [0.05, 0.56, 0.60, 0.25],
                "rows_per_page": 1,
                "overflow": "new_page",
                "columns": [
                    {"source": "component", "header": "Item", "width_norm": 0.50},
                    {"source": "qty", "header": "Qty", "width_norm": 0.25},
                    {"source": "unit", "header": "Unit", "width_norm": 0.25},
                ],
            }
        ],
    }

    result = render_pdf_overlay_for_report(report, template, output, template_dir=tmp_path)

    assert result["ok"] is True
    assert output.exists()
    assert result["pdf_validation"]["pages"] == 3
    assert result["summary"]["rows"] == 3
    assert result["dry_run"]["placements"][0]["render_pages"] == 3
    reader = PdfReader(str(output))
    assert len(reader.pages) == 3
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Pipe" in text
    assert "Elbow" in text
    assert "Tee" in text


def test_render_pdf_overlay_table_image_cells_paginate(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    output = tmp_path / "photo_grid.pdf"
    _write_base_pdf(base_pdf, width=500, height=500)
    photos = []
    for idx in range(3):
        image = tmp_path / f"before_{idx}.png"
        _write_image(image)
        photos.append({"path": str(image), "name": f"before_{idx}.png"})
    report = _report(Path(photos[0]["path"]))
    report["photos"]["before"] = photos
    template = {
        "kind": "pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "base_pdf": str(base_pdf),
        "coordinate_space": "normalized",
        "fields": [
            {
                "type": "table",
                "source": "photos.before[*]",
                "page": 1,
                "rect_norm": [0.05, 0.08, 0.90, 0.80],
                "rows_per_page": 2,
                "row_height_pt": 120,
                "header_height_pt": 20,
                "overflow": "new_page",
                "columns": [
                    {"source": "path", "header": "Photo", "cell_type": "image", "fit": "contain", "width_norm": 0.70},
                    {"source": "name", "header": "Name", "width_norm": 0.30},
                ],
            }
        ],
    }

    result = render_pdf_overlay_for_report(report, template, output, template_dir=tmp_path)

    assert result["ok"] is True
    assert result["pdf_validation"]["pages"] == 2
    assert result["summary"]["rows"] == 3
    assert result["summary"]["image"] == 3
    assert result["dry_run"]["placements"][0]["image_cell_count"] == 3
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(output)).pages)
    assert "before_0.png" in text
    assert "before_2.png" in text


def test_render_pdf_overlay_table_image_cell_missing_file_is_warning(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    output = tmp_path / "photo_missing.pdf"
    _write_base_pdf(base_pdf)
    image = tmp_path / "before.png"
    _write_image(image)
    report = _report(image)
    report["photos"]["before"] = [{"path": str(tmp_path / "missing.png"), "name": "missing.png"}]
    template = {
        "kind": "pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "base_pdf": str(base_pdf),
        "coordinate_space": "normalized",
        "fields": [
            {
                "type": "table",
                "source": "photos.before[*]",
                "page": 1,
                "rect_norm": [0.05, 0.08, 0.90, 0.50],
                "rows_per_page": 1,
                "row_height_pt": 70,
                "overflow": "new_page",
                "columns": [
                    {"source": "path", "header": "Photo", "cell_type": "image", "width_norm": 0.70},
                    {"source": "name", "header": "Name", "width_norm": 0.30},
                ],
            }
        ],
    }

    result = render_pdf_overlay_for_report(report, template, output, template_dir=tmp_path)
    warnings = [issue for issue in result["issues"] if issue["code"] == "missing_image_file"]

    assert result["ok"] is True
    assert output.exists()
    assert result["summary"]["image"] == 1
    assert warnings
    assert all(issue["severity"] == "warning" for issue in warnings)


def test_render_pdf_overlay_table_new_page_can_use_continuation_page(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    image = tmp_path / "before.png"
    output = tmp_path / "continuation.pdf"
    _write_two_page_base_pdf(base_pdf)
    _write_image(image)
    report = _report(image)
    report["materials"]["rows"] = [
        {"component": "Pipe", "qty": 2, "unit": "M"},
        {"component": "Elbow", "qty": 1, "unit": "EA"},
    ]
    template = {
        "kind": "pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "base_pdf": str(base_pdf),
        "coordinate_space": "normalized",
        "fields": [
            {
                "type": "table",
                "source": "materials.rows",
                "page": 1,
                "continuation_page": 2,
                "rect_norm": [0.05, 0.56, 0.60, 0.25],
                "rows_per_page": 1,
                "overflow": "new_page",
                "columns": [
                    {"source": "component", "header": "Item", "width_norm": 0.50},
                    {"source": "qty", "header": "Qty", "width_norm": 0.25},
                    {"source": "unit", "header": "Unit", "width_norm": 0.25},
                ],
            }
        ],
    }

    result = render_pdf_overlay_for_report(report, template, output, template_dir=tmp_path)

    assert result["ok"] is True
    reader = PdfReader(str(output))
    assert len(reader.pages) == 3
    assert float(reader.pages[0].mediabox.width) == 400
    assert float(reader.pages[1].mediabox.width) == 300
    assert float(reader.pages[2].mediabox.width) == 300


def test_render_pdf_overlay_reports_unsupported_table_truncate_before_output(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    image = tmp_path / "before.png"
    output = tmp_path / "table_truncate.pdf"
    _write_base_pdf(base_pdf)
    _write_image(image)
    report = _report(image)
    report["materials"]["rows"] = [
        {"component": "Pipe", "qty": 2, "unit": "M"},
        {"component": "Elbow", "qty": 1, "unit": "EA"},
    ]
    template = {
        "kind": "pdf_overlay",
        "schema_version": "template_mapping.v1",
        "target_schema_version": "pdf_overlay.v1",
        "base_pdf": str(base_pdf),
        "coordinate_space": "normalized",
        "fields": [
            {
                "type": "table",
                "source": "materials.rows",
                "page": 1,
                "rect_norm": [0.05, 0.56, 0.60, 0.25],
                "rows_per_page": 1,
                "overflow": "truncate",
                "columns": [
                    {"source": "component", "header": "Item", "width_norm": 0.50},
                    {"source": "qty", "header": "Qty", "width_norm": 0.25},
                    {"source": "unit", "header": "Unit", "width_norm": 0.25},
                ],
            }
        ],
    }

    result = render_pdf_overlay_for_report(report, template, output, template_dir=tmp_path)
    codes = [issue["code"] for issue in result["issues"]]

    assert result["ok"] is False
    assert not output.exists()
    assert "overflow_mode_unsupported" in codes


def test_render_pdf_overlay_rejects_table_row_height_overflow_without_output(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    image = tmp_path / "before.png"
    output = tmp_path / "row_height.pdf"
    _write_base_pdf(base_pdf)
    _write_image(image)
    template = _template(str(base_pdf))
    template["fields"] = [
        {
            "type": "table",
            "source": "materials.rows",
            "page": 1,
            "rect_norm": [0.05, 0.56, 0.60, 0.10],
            "rows_per_page": 1,
            "row_height_pt": 80,
            "overflow": "error",
            "columns": [
                {"source": "component", "header": "Item", "width_norm": 0.50},
                {"source": "qty", "header": "Qty", "width_norm": 0.25},
                {"source": "unit", "header": "Unit", "width_norm": 0.25},
            ],
        }
    ]

    result = render_pdf_overlay_for_report(_report(image), template, output, template_dir=tmp_path)

    assert result["ok"] is False
    assert not output.exists()
    assert any(issue["code"] == "table_row_height_overflow" for issue in result["issues"])


def test_pdf_overlay_geometry_uses_cropbox_visible_area(tmp_path):
    base_pdf = tmp_path / "crop.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=300)
    page.cropbox.lower_left = (50, 40)
    page.cropbox.upper_right = (350, 260)
    with open(base_pdf, "wb") as f:
        writer.write(f)
    page = PdfReader(str(base_pdf)).pages[0]

    geometry = pdf_overlay_renderer._page_geometry(page)
    rect = pdf_overlay_renderer._rect_to_points({"rect_norm": [0.10, 0.20, 0.30, 0.40]}, geometry)

    assert geometry["crop_left"] == 50
    assert geometry["crop_bottom"] == 40
    assert geometry["crop_width"] == 300
    assert geometry["crop_height"] == 220
    assert rect["left"] == 80
    assert rect["width"] == 90
    assert rect["height"] == 88
    assert rect["bottom"] == 128


def test_render_pdf_overlay_transfers_page_rotation_before_overlay(tmp_path):
    base_pdf = tmp_path / "rotated.pdf"
    image = tmp_path / "before.png"
    output = tmp_path / "rotated_out.pdf"
    _write_rotated_base_pdf(base_pdf)
    _write_image(image)
    template = _template(str(base_pdf))
    template["fields"] = [
        {
            "type": "text",
            "source": "report.report_id",
            "page": 1,
            "rect_norm": [0.08, 0.08, 0.30, 0.08],
            "overflow": "shrink",
        }
    ]

    result = render_pdf_overlay_for_report(_report(image), template, output, template_dir=tmp_path)

    assert result["ok"] is True
    reader = PdfReader(str(output))
    page = reader.pages[0]
    assert int(page.get("/Rotate", 0) or 0) == 0
    assert float(page.mediabox.width) == 300
    assert float(page.mediabox.height) == 400
    assert "R-PDF" in (page.extract_text() or "")


def _usable_pdftoppm() -> str:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        pytest.skip("pdftoppm is not available")
    try:
        probe = subprocess.run(
            [pdftoppm, "-v"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"pdftoppm is not executable: {exc}")
    if probe.returncode != 0:
        message = (probe.stderr or probe.stdout or "").strip()
        pytest.skip(f"pdftoppm is not executable: {message or probe.returncode}")
    return pdftoppm


def test_render_pdf_overlay_rotated_page_debug_rect_visual_position(tmp_path):
    pdftoppm = _usable_pdftoppm()

    base_pdf = tmp_path / "rotated.pdf"
    image = tmp_path / "before.png"
    output = tmp_path / "rotated_visual.pdf"
    png_prefix = tmp_path / "rotated_visual"
    png_path = tmp_path / "rotated_visual.png"
    _write_rotated_base_pdf(base_pdf)
    _write_image(image)
    template = _template(str(base_pdf))
    template["debug"] = True
    template["fields"] = [
        {
            "type": "text",
            "source": "report.report_id",
            "page": 1,
            "rect_norm": [0.08, 0.08, 0.30, 0.08],
            "overflow": "shrink",
        }
    ]
    result = render_pdf_overlay_for_report(_report(image), template, output, template_dir=tmp_path)
    assert result["ok"] is True

    subprocess.run(
        [pdftoppm, "-png", "-singlefile", str(output), str(png_prefix)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert png_path.exists()
    red_bbox = _red_pixel_bbox(png_path)
    assert red_bbox is not None
    x0, y0, x1, y1 = red_bbox
    with Image.open(png_path) as image_data:
        width, height = image_data.size
    assert height > width
    assert x0 < width * 0.20
    assert y0 < height * 0.20
    assert x1 < width * 0.55
    assert y1 < height * 0.25


def _red_pixel_bbox(path: Path):
    with Image.open(path).convert("RGB") as image:
        pixels = image.load()
        xs = []
        ys = []
        for y in range(image.height):
            for x in range(image.width):
                r, g, b = pixels[x, y]
                if r > 180 and g < 80 and b < 80:
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return None
        return min(xs), min(ys), max(xs), max(ys)
