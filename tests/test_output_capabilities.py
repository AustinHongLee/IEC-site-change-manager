# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import output_capabilities
from capabilities import CapabilityResult


def test_output_capability_report_lists_core_outputs(monkeypatch):
    monkeypatch.setattr(output_capabilities, "get_soffice_path", lambda: "")
    monkeypatch.setattr(
        output_capabilities,
        "detect_libreoffice",
        lambda executable=None, check_version=False: CapabilityResult(
            name="libreoffice",
            available=False,
            reason="找不到 LibreOffice/soffice 執行檔",
            detail="missing",
        ),
    )

    report = output_capabilities.build_output_capability_report()
    by_key = {item["key"]: item for item in report["capabilities"]}

    assert report["ok"] is True
    assert by_key["site_statistics_xlsx"]["available"] is True
    assert by_key["xlsx_template"]["available"] is True
    assert by_key["pdf_overlay"]["available"] is True
    assert by_key["pdf_overlay"]["status"] == "minimal"
    assert by_key["workbook_pdf_libreoffice"]["available"] is False
    assert by_key["workbook_pdf_libreoffice"]["optional"] is True
    assert any("LibreOffice" in item for item in report["recommendations"])


def test_output_capability_report_uses_configured_soffice_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(output_capabilities, "get_soffice_path", lambda: "C:/configured/soffice.exe")

    def fake_detect(executable=None, check_version=False):
        captured["executable"] = executable
        captured["check_version"] = check_version
        return CapabilityResult(
            name="libreoffice",
            available=True,
            reason="找到 LibreOffice/soffice 執行檔，尚未執行版本探測",
            executable="C:/configured/soffice.exe",
        )

    monkeypatch.setattr(output_capabilities, "detect_libreoffice", fake_detect)

    report = output_capabilities.build_output_capability_report(probe_libreoffice_version=False)
    pdf = {item["key"]: item for item in report["capabilities"]}["workbook_pdf_libreoffice"]

    assert captured == {"executable": "C:/configured/soffice.exe", "check_version": False}
    assert pdf["available"] is True
    assert pdf["status"] == "found_unprobed"
    assert "settings paths.soffice_path=C:/configured/soffice.exe" in pdf["detail"]
