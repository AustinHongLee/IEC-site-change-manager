# -*- coding: utf-8 -*-
"""Renderer registry for canonical report outputs.

The registry is the routing boundary between template ``kind`` values and
renderer backends. It must stay COM-free at import time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from capabilities import detect_excel_com
from output_result import attach_output_envelope, output_item, step_item


@dataclass(frozen=True)
class RendererDescriptor:
    kind: str
    label: str
    available: bool
    status: str
    data_contract: str
    template_driven: bool
    legacy: bool
    reason: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_renderers(*, probe_com_application: bool = False) -> list[dict[str, Any]]:
    return [
        _xlsx_template_descriptor().to_dict(),
        _pdf_overlay_descriptor().to_dict(),
        _xlsx_com_descriptor(probe_com_application=probe_com_application).to_dict(),
    ]


def get_renderer_descriptor(
    kind: str,
    *,
    probe_com_application: bool = False,
) -> dict[str, Any]:
    normalized = _normalize_kind(kind)
    for renderer in list_renderers(probe_com_application=probe_com_application):
        if renderer["kind"] == normalized:
            return renderer
    return {
        "kind": normalized,
        "label": normalized or "<空白>",
        "available": False,
        "status": "unknown",
        "data_contract": "",
        "template_driven": False,
        "legacy": False,
        "reason": f"未知 renderer kind：{normalized or '<空白>'}",
        "detail": "",
    }


def render_with_template(
    report: dict[str, Any],
    template: dict[str, Any],
    output_path: str,
    *,
    template_dir: str | None = None,
) -> dict[str, Any]:
    kind = _normalize_kind(template.get("kind") or "xlsx_template")
    if kind == "xlsx_template":
        from xlsx_template_renderer import render_xlsx_template_for_report

        result = render_xlsx_template_for_report(
            report,
            template,
            output_path,
            template_dir=template_dir,
        )
        result["renderer"] = _xlsx_template_descriptor().to_dict()
        attach_output_envelope(
            result,
            outputs=[
                output_item(
                    kind="xlsx_template",
                    path=result.get("path", ""),
                    role="primary",
                    label="Excel template workbook",
                )
            ],
            capabilities={"renderer": result["renderer"]},
            steps=[
                step_item(
                    key="xlsx_template_render",
                    ok=result.get("ok", False),
                    label="Render xlsx_template workbook",
                )
            ],
        )
        return result
    if kind == "xlsx_com":
        descriptor = _xlsx_com_descriptor(probe_com_application=True).to_dict()
        issue = {
            "severity": "error",
            "code": "renderer_not_canonical_ready",
            "field_index": 0,
            "source": "",
            "message": (
                "xlsx_com 已登錄為舊版可選後端，但尚未完成 CanonicalReport adapter；"
                "請先使用 xlsx_template 或舊版 GUI 產出流程。"
            ),
        }
        if not descriptor["available"]:
            issue["code"] = "renderer_unavailable"
            issue["message"] = format_renderer_unavailable(descriptor)
        return attach_output_envelope({
            "ok": False,
            "path": "",
            "renderer": descriptor,
            "summary": {"text": 0, "image": 0, "table": 0, "rows": 0},
            "issues": [issue],
        }, capabilities={"renderer": descriptor})
    if kind == "pdf_overlay":
        from pdf_overlay_renderer import render_pdf_overlay_for_report

        descriptor = _pdf_overlay_descriptor().to_dict()
        result = render_pdf_overlay_for_report(
            report,
            template,
            output_path,
            template_dir=template_dir,
        )
        result["renderer"] = descriptor
        attach_output_envelope(
            result,
            outputs=result.get("outputs", []),
            capabilities={"renderer": descriptor},
            steps=result.get("steps", []),
        )
        return result
    descriptor = get_renderer_descriptor(kind)
    return attach_output_envelope({
        "ok": False,
        "path": "",
        "renderer": descriptor,
        "summary": {"text": 0, "image": 0, "table": 0, "rows": 0},
        "issues": [{
            "severity": "error",
            "code": "renderer_unknown",
            "field_index": 0,
            "source": "",
            "message": descriptor["reason"],
        }],
    }, capabilities={"renderer": descriptor})


def format_renderer_unavailable(renderer: dict[str, Any]) -> str:
    kind = str(renderer.get("kind", "") or "")
    detail = f"\n\n技術細節：{renderer.get('detail')}" if renderer.get("detail") else ""
    if kind == "xlsx_com":
        return (
            "舊版修改單產出需要 Microsoft Excel / pywin32 的 COM 後端，"
            "但目前環境無法使用。\n\n"
            f"狀態：{renderer.get('status', '')}\n"
            f"原因：{renderer.get('reason', '')}\n\n"
            "你仍可使用不依賴 COM 的功能，例如健康檢查、現場統計單、"
            "template validate / dry-run / xlsx_template render。"
            f"{detail}"
        )
    return (
        f"輸出後端 {kind or '<空白>'} 目前不可用。\n\n"
        f"原因：{renderer.get('reason', '')}"
        f"{detail}"
    )


def _xlsx_template_descriptor() -> RendererDescriptor:
    return RendererDescriptor(
        kind="xlsx_template",
        label="Excel 模板（openpyxl）",
        available=True,
        status="ready",
        data_contract="CanonicalReport",
        template_driven=True,
        legacy=False,
        reason="純 openpyxl，COM-free",
        detail="支援 text / image / table、dry-run、layout validation、post validation",
    )


def _pdf_overlay_descriptor() -> RendererDescriptor:
    return RendererDescriptor(
        kind="pdf_overlay",
        label="PDF Overlay 模板",
        available=True,
        status="minimal",
        data_contract="report.v1 + template_mapping.v1 + pdf_overlay.v1",
        template_driven=True,
        legacy=False,
        reason="最小垂直切片可用",
        detail="支援 base PDF 疊 text/image/table/debug rect、CropBox、/Rotate、text overflow fail-fast 與 table overflow=new_page；truncate 仍明確 unsupported",
    )


def _xlsx_com_descriptor(*, probe_com_application: bool = False) -> RendererDescriptor:
    capability = detect_excel_com(probe_application=probe_com_application)
    if capability.available and not probe_com_application:
        status = "unprobed"
        available = False
        reason = "pywin32 模組可載入，尚未啟動 Excel 探測"
        detail = _join_detail(
            "未確認 Excel Application 可啟動",
            "CanonicalReport adapter 尚未完成；舊 GUI 產出流程仍保留",
        )
        return RendererDescriptor(
            kind="xlsx_com",
            label="舊版 Excel COM 模板",
            available=available,
            status=status,
            data_contract="legacy_folder_args; CanonicalReport adapter pending",
            template_driven=False,
            legacy=True,
            reason=reason,
            detail=detail,
        )
    status = "legacy_available" if capability.available else "unavailable"
    reason = capability.reason or ("Excel COM 可用" if capability.available else "Excel COM 不可用")
    detail = capability.detail
    if capability.available:
        detail = _join_detail(detail, "CanonicalReport adapter 尚未完成；舊 GUI 產出流程仍保留")
    return RendererDescriptor(
        kind="xlsx_com",
        label="舊版 Excel COM 模板",
        available=capability.available,
        status=status,
        data_contract="legacy_folder_args; CanonicalReport adapter pending",
        template_driven=False,
        legacy=True,
        reason=reason,
        detail=detail,
    )


def _join_detail(*parts: str) -> str:
    return "；".join(part for part in parts if part)


def _normalize_kind(kind: Any) -> str:
    return str(kind or "").strip()
