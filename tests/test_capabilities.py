# -*- coding: utf-8 -*-

import builtins
import os
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import subprocess

from capabilities import (
    _excel_com_cache,
    _libreoffice_cache,
    detect_excel_com,
    detect_libreoffice,
)


def test_detect_excel_com_reports_unavailable_when_pywin32_is_missing(monkeypatch):
    for name in list(sys.modules):
        if name == "pythoncom" or name == "win32com" or name.startswith("win32com."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pythoncom" or name == "win32com" or name.startswith("win32com."):
            raise ImportError(f"blocked optional COM module: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    result = detect_excel_com(force_refresh=True)

    assert result.available is False
    assert result.name == "excel_com"
    assert "pythoncom" in result.reason
    _excel_com_cache.clear()


def test_gui_and_excel_handler_import_without_com_modules():
    repo = Path(__file__).resolve().parents[1]
    control_dir = repo / "control"
    script = f"""
import builtins
import sys

sys.path.insert(0, {str(control_dir)!r})
real_import = builtins.__import__

def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "pythoncom" or name == "win32com" or name.startswith("win32com."):
        raise ImportError("COM import blocked during import-guard test")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = blocked_import

import excel_handler
import gui

loaded = [
    name for name in sys.modules
    if name == "pythoncom" or name == "win32com" or name.startswith("win32com.")
]
assert loaded == [], loaded
assert hasattr(excel_handler, "generate_report")
assert hasattr(gui, "MainWindow")
assert gui.CHANGE_ORDER_WIZARD_AVAILABLE is True
assert hasattr(gui.MainWindow, "_launch_change_order_wizard")
print("ok")
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_detect_libreoffice_reports_unavailable_when_executable_is_missing(monkeypatch):
    import capabilities

    _libreoffice_cache.clear()
    monkeypatch.setattr(capabilities.shutil, "which", lambda _: None)
    monkeypatch.setattr(capabilities.os.path, "exists", lambda _: False)

    result = detect_libreoffice(force_refresh=True)

    assert result.available is False
    assert result.name == "libreoffice"
    assert "找不到" in result.reason
    _libreoffice_cache.clear()


def test_detect_libreoffice_accepts_version_probe(monkeypatch):
    import capabilities

    _libreoffice_cache.clear()
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "C:/fake/soffice.exe" if name == "soffice" else None)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="LibreOffice 7.6\n", stderr="")

    monkeypatch.setattr(capabilities.subprocess, "run", fake_run)

    result = detect_libreoffice(force_refresh=True)

    assert result.available is True
    assert result.executable == "C:/fake/soffice.exe"
    assert result.detail == "LibreOffice 7.6"
    _libreoffice_cache.clear()
