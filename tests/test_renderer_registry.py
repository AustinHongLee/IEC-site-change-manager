# -*- coding: utf-8 -*-

import builtins
import os
import sys

from openpyxl import load_workbook
from pypdf import PdfReader, PdfWriter


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import renderer_registry
from capabilities import CapabilityResult, _excel_com_cache
from renderer_registry import list_renderers, render_with_template


def _report():
    return {
        "report": {"report_id": "R-REG", "description": "registry render"},
        "materials": {"rows": [{"component": "Pipe (管)", "qty": 2}]},
    }


def test_registry_lists_template_renderer_and_optional_com(monkeypatch):
    _excel_com_cache.clear()
    for name in list(sys.modules):
        if name == "pythoncom" or name == "win32com" or name.startswith("win32com."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pythoncom" or name == "win32com" or name.startswith("win32com."):
            raise ImportError(f"blocked optional COM module: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    renderers = {item["kind"]: item for item in list_renderers()}

    assert renderers["xlsx_template"]["available"] is True
    assert renderers["xlsx_template"]["data_contract"] == "CanonicalReport"
    assert renderers["pdf_overlay"]["available"] is True
    assert renderers["pdf_overlay"]["status"] == "minimal"
    assert renderers["xlsx_com"]["available"] is False
    assert renderers["xlsx_com"]["legacy"] is True
    assert "pythoncom" in renderers["xlsx_com"]["reason"]
    _excel_com_cache.clear()


def test_registry_dispatches_xlsx_template_renderer(tmp_path):
    output = tmp_path / "registry.xlsx"
    template = {
        "kind": "xlsx_template",
        "fields": [
            {"type": "text", "source": "report.report_id", "cell": "A1"},
            {
                "type": "table",
                "source": "materials.rows",
                "start_cell": "A5",
                "max_rows": 5,
                "columns": ["component", "qty"],
            },
        ],
    }

    result = render_with_template(_report(), template, str(output))

    assert result["ok"] is True
    assert result["renderer"]["kind"] == "xlsx_template"
    wb = load_workbook(output, data_only=False)
    try:
        assert wb.active["A1"].value == "R-REG"
        assert wb.active["A5"].value == "Pipe (管)"
        assert wb.active["B5"].value == 2
    finally:
        wb.close()


def test_registry_rejects_xlsx_com_until_canonical_adapter_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(
        renderer_registry,
        "detect_excel_com",
        lambda probe_application=False: CapabilityResult(
            name="excel_com",
            available=True,
            reason="Excel COM 可用",
            detail="mocked",
        ),
    )

    result = render_with_template(_report(), {"kind": "xlsx_com", "fields": []}, str(tmp_path / "out.xlsx"))

    assert result["ok"] is False
    assert result["renderer"]["kind"] == "xlsx_com"
    assert result["renderer"]["available"] is True
    assert result["issues"][0]["code"] == "renderer_not_canonical_ready"


def test_registry_dispatches_pdf_overlay_renderer(tmp_path):
    base_pdf = tmp_path / "base.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    with open(base_pdf, "wb") as f:
        writer.write(f)
    result = render_with_template(
        _report(),
        {
            "kind": "pdf_overlay",
            "schema_version": "template_mapping.v1",
            "target_schema_version": "pdf_overlay.v1",
            "base_pdf": str(base_pdf),
            "coordinate_space": "normalized",
            "fields": [
                {
                    "type": "text",
                    "source": "report.report_id",
                    "page": 1,
                    "rect_norm": [0.05, 0.05, 0.40, 0.10],
                    "overflow": "shrink",
                },
            ],
        },
        str(tmp_path / "out.pdf"),
    )

    assert result["ok"] is True
    assert result["renderer"]["kind"] == "pdf_overlay"
    assert result["renderer"]["status"] == "minimal"
    assert result["outputs"][0]["kind"] == "pdf_overlay"
    assert "R-REG" in (PdfReader(result["path"]).pages[0].extract_text() or "")


def test_registry_rejects_unknown_renderer_kind(tmp_path):
    result = render_with_template(_report(), {"kind": "not_a_renderer", "fields": []}, str(tmp_path / "out.pdf"))

    assert result["ok"] is False
    assert result["renderer"]["kind"] == "not_a_renderer"
    assert result["issues"][0]["code"] == "renderer_unknown"
