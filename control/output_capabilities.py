# -*- coding: utf-8 -*-
"""Preflight report for output paths used by the app and CLI tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from capabilities import detect_libreoffice
from renderer_registry import get_renderer_descriptor
from settings_manager import get_soffice_path


@dataclass(frozen=True)
class OutputCapability:
    key: str
    label: str
    available: bool
    status: str
    category: str
    optional: bool
    reason: str = ""
    detail: str = ""
    executable: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_output_capability_report(
    *,
    probe_com_application: bool = False,
    probe_libreoffice_version: bool = False,
) -> dict[str, Any]:
    capabilities = [
        _site_statistics_xlsx_capability().to_dict(),
        _xlsx_template_capability().to_dict(),
        _pdf_overlay_capability().to_dict(),
        _libreoffice_pdf_capability(probe_version=probe_libreoffice_version).to_dict(),
        _legacy_xlsx_com_capability(probe_com_application=probe_com_application).to_dict(),
    ]
    required = [item for item in capabilities if not item["optional"]]
    blocking = [item for item in required if not item["available"]]
    attention = [
        item for item in capabilities
        if not item["available"] and (not item["optional"] or item["category"] == "pdf_postprocessor")
    ]
    return {
        "ok": not blocking,
        "summary": {
            "total": len(capabilities),
            "available": sum(1 for item in capabilities if item["available"]),
            "attention": len(attention),
            "blocking": len(blocking),
        },
        "capabilities": capabilities,
        "recommendations": _recommendations(capabilities),
    }


def _site_statistics_xlsx_capability() -> OutputCapability:
    return OutputCapability(
        key="site_statistics_xlsx",
        label="現場統計單 Excel",
        available=True,
        status="ready",
        category="workbook",
        optional=False,
        reason="openpyxl exporter ready",
        detail="可輸出總覽、修改單清單、焊口統計、照片表、用料統計與問題清單",
    )


def _xlsx_template_capability() -> OutputCapability:
    renderer = get_renderer_descriptor("xlsx_template")
    return OutputCapability(
        key="xlsx_template",
        label="xlsx_template 模板輸出",
        available=bool(renderer.get("available")),
        status=str(renderer.get("status", "")),
        category="renderer",
        optional=False,
        reason=str(renderer.get("reason", "")),
        detail=str(renderer.get("detail", "")),
    )


def _pdf_overlay_capability() -> OutputCapability:
    renderer = get_renderer_descriptor("pdf_overlay")
    return OutputCapability(
        key="pdf_overlay",
        label="PDF Overlay 模板輸出",
        available=bool(renderer.get("available")),
        status=str(renderer.get("status", "")),
        category="renderer",
        optional=True,
        reason=str(renderer.get("reason", "")),
        detail=str(renderer.get("detail", "")),
    )


def _libreoffice_pdf_capability(*, probe_version: bool) -> OutputCapability:
    configured = get_soffice_path() or None
    capability = detect_libreoffice(executable=configured, check_version=probe_version)
    status = "ready" if capability.available and probe_version else "found_unprobed" if capability.available else "unavailable"
    detail = capability.detail
    if configured:
        detail = _join_detail(detail, f"settings paths.soffice_path={configured}")
    return OutputCapability(
        key="workbook_pdf_libreoffice",
        label="非 COM PDF 轉檔（LibreOffice）",
        available=capability.available,
        status=status,
        category="pdf_postprocessor",
        optional=True,
        reason=capability.reason,
        detail=detail,
        executable=capability.executable,
    )


def _legacy_xlsx_com_capability(*, probe_com_application: bool) -> OutputCapability:
    renderer = get_renderer_descriptor("xlsx_com", probe_com_application=probe_com_application)
    return OutputCapability(
        key="legacy_xlsx_com",
        label="舊版 Excel COM 產出",
        available=bool(renderer.get("available")),
        status=str(renderer.get("status", "")),
        category="legacy_renderer",
        optional=True,
        reason=str(renderer.get("reason", "")),
        detail=str(renderer.get("detail", "")),
    )


def _recommendations(capabilities: list[dict[str, Any]]) -> list[str]:
    by_key = {item["key"]: item for item in capabilities}
    recs: list[str] = []
    pdf = by_key.get("workbook_pdf_libreoffice", {})
    if not pdf.get("available"):
        recs.append("若要輸出非 COM PDF，請安裝 LibreOffice，或到設定頁指定 soffice.exe。")
    legacy = by_key.get("legacy_xlsx_com", {})
    if not legacy.get("available"):
        recs.append("舊版 Excel COM 產出不可用時，請優先使用現場統計單或 xlsx_template 路線。")
    if not recs:
        recs.append("主要輸出能力可用；若要交付 PDF，仍建議抽查版面。")
    return recs


def _join_detail(*parts: str) -> str:
    return "；".join(str(part) for part in parts if str(part or "").strip())
