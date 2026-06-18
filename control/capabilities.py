# -*- coding: utf-8 -*-
"""Runtime capability probes for optional integrations.

This module must stay dependency-light: importing it should never import Excel
COM, LibreOffice, or any renderer backend.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityResult:
    name: str
    available: bool
    reason: str = ""
    detail: str = ""
    executable: str = ""


_excel_com_cache: dict[bool, CapabilityResult] = {}
_libreoffice_cache: dict[tuple[str, bool], CapabilityResult] = {}

_LIBREOFFICE_COMMANDS = ("soffice", "soffice.exe", "libreoffice", "libreoffice.exe")
_LIBREOFFICE_WINDOWS_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


def detect_excel_com(
    *,
    probe_application: bool = True,
    force_refresh: bool = False,
) -> CapabilityResult:
    """Return whether the legacy Excel COM backend can be used.

    ``probe_application=True`` starts a hidden Excel instance once and quits it.
    Use the cached result for UI/CLI decisions so the probe does not repeatedly
    launch Excel.
    """
    cache_key = bool(probe_application)
    if not force_refresh and cache_key in _excel_com_cache:
        return _excel_com_cache[cache_key]

    try:
        import pythoncom  # noqa: F401
    except Exception as exc:
        return _remember_excel_com(
            cache_key,
            CapabilityResult(
                name="excel_com",
                available=False,
                reason="缺少 pywin32 的 pythoncom 模組",
                detail=str(exc),
            ),
        )

    try:
        import win32com.client as win32_client
    except Exception as exc:
        return _remember_excel_com(
            cache_key,
            CapabilityResult(
                name="excel_com",
                available=False,
                reason="缺少 pywin32 的 win32com 模組",
                detail=str(exc),
            ),
        )

    if not probe_application:
        return _remember_excel_com(
            cache_key,
            CapabilityResult(
                name="excel_com",
                available=True,
                reason="pywin32 模組可載入，尚未啟動 Excel 探測",
            ),
        )

    excel = None
    try:
        excel = win32_client.DispatchEx("Excel.Application")
        try:
            excel.Visible = False
        except Exception:
            pass
        try:
            excel.DisplayAlerts = False
        except Exception:
            pass
        version = ""
        try:
            version = str(excel.Version)
        except Exception:
            pass
        return _remember_excel_com(
            cache_key,
            CapabilityResult(
                name="excel_com",
                available=True,
                reason="Excel COM 可用",
                detail=f"Excel version: {version}" if version else "",
            ),
        )
    except Exception as exc:
        return _remember_excel_com(
            cache_key,
            CapabilityResult(
                name="excel_com",
                available=False,
                reason="無法啟動 Excel COM",
                detail=str(exc),
            ),
        )
    finally:
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass


def format_excel_com_unavailable(result: CapabilityResult | None = None) -> str:
    result = result or detect_excel_com()
    reason = result.reason or "Excel COM 不可用"
    detail = f"\n\n技術細節：{result.detail}" if result.detail else ""
    return (
        "舊版修改單產出需要 Microsoft Excel / pywin32 的 COM 後端，"
        "但目前環境無法使用。\n\n"
        f"原因：{reason}\n\n"
        "你仍可使用不依賴 COM 的功能，例如健康檢查、現場統計單、"
        "template validate / dry-run / xlsx_template render。"
        f"{detail}"
    )


def detect_libreoffice(
    *,
    executable: str | None = None,
    check_version: bool = True,
    force_refresh: bool = False,
) -> CapabilityResult:
    """Return whether LibreOffice headless conversion is available."""
    executable_key = str(executable or "").strip()
    cache_key = (executable_key, bool(check_version))
    if not force_refresh and cache_key in _libreoffice_cache:
        return _libreoffice_cache[cache_key]

    soffice = _resolve_libreoffice_executable(executable_key)
    if not soffice:
        return _remember_libreoffice(
            cache_key,
            CapabilityResult(
                name="libreoffice",
                available=False,
                reason="找不到 LibreOffice/soffice 執行檔",
                detail="請安裝 LibreOffice，或設定 soffice.exe 路徑。",
            ),
        )

    if not check_version:
        return _remember_libreoffice(
            cache_key,
            CapabilityResult(
                name="libreoffice",
                available=True,
                reason="找到 LibreOffice/soffice 執行檔，尚未執行版本探測",
                executable=soffice,
            ),
        )

    try:
        completed = subprocess.run(
            [soffice, "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        return _remember_libreoffice(
            cache_key,
            CapabilityResult(
                name="libreoffice",
                available=False,
                reason="無法執行 LibreOffice/soffice",
                detail=str(exc),
                executable=soffice,
            ),
        )

    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        return _remember_libreoffice(
            cache_key,
            CapabilityResult(
                name="libreoffice",
                available=False,
                reason="LibreOffice 版本探測失敗",
                detail=output,
                executable=soffice,
            ),
        )

    return _remember_libreoffice(
        cache_key,
        CapabilityResult(
            name="libreoffice",
            available=True,
            reason="LibreOffice headless 可用",
            detail=output.splitlines()[0] if output else "",
            executable=soffice,
        ),
    )


def format_libreoffice_unavailable(result: CapabilityResult | None = None) -> str:
    result = result or detect_libreoffice()
    reason = result.reason or "LibreOffice 不可用"
    detail = f"\n\n技術細節：{result.detail}" if result.detail else ""
    return (
        "非 COM PDF 轉檔需要 LibreOffice headless，但目前環境無法使用。\n\n"
        f"原因：{reason}\n\n"
        "你仍可產出 Excel 檔，或在安裝 LibreOffice 後重新偵測。"
        f"{detail}"
    )


def _remember_excel_com(cache_key: bool, result: CapabilityResult) -> CapabilityResult:
    _excel_com_cache[cache_key] = result
    return result


def _remember_libreoffice(cache_key: tuple[str, bool], result: CapabilityResult) -> CapabilityResult:
    _libreoffice_cache[cache_key] = result
    return result


def _resolve_libreoffice_executable(executable: str) -> str:
    if executable:
        if os.path.exists(executable):
            return os.path.abspath(executable)
        found = shutil.which(executable)
        return found or ""
    for command in _LIBREOFFICE_COMMANDS:
        found = shutil.which(command)
        if found:
            return found
    for path in _LIBREOFFICE_WINDOWS_PATHS:
        if os.path.exists(path):
            return path
    return ""
