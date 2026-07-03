# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path


def test_core_and_gui_imports_do_not_require_com_modules():
    repo = Path(__file__).resolve().parents[1]
    control_dir = repo / "control"
    modules = [
        "capabilities",
        "renderer_registry",
        "output_capabilities",
        "output_result",
        "canonical_fields",
        "canonical_report",
        "template_mapping",
        "template_dry_run",
        "pdf_overlay_schema",
        "pdf_overlay_renderer",
        "xlsx_template_renderer",
        "workbook_pdf_converter",
        "demo_smoke",
        "site_statistics_exporter",
        "owner_data_report",
        "record_manager",
        "project_guard",
        "gui",
    ]
    script = f"""
import builtins
import importlib
import sys

sys.path.insert(0, {str(control_dir)!r})
real_import = builtins.__import__
blocked_attempts = []

def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "pythoncom" or name == "win32com" or name.startswith("win32com."):
        blocked_attempts.append(name)
        raise ImportError("COM import blocked during import-guard test: " + name)
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = blocked_import
modules = {modules!r}
for module_name in modules:
    importlib.import_module(module_name)

loaded = [
    name for name in sys.modules
    if name == "pythoncom" or name == "win32com" or name.startswith("win32com.")
]
assert loaded == [], loaded
assert blocked_attempts == [], blocked_attempts
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
