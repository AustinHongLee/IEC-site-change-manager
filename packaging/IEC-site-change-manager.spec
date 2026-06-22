# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path(SPECPATH).resolve().parent


def asset(src: str, dest: str):
    return (str(ROOT / src), dest)


datas = [
    asset("template", "template"),
    asset("control/image", "control/image"),
    asset("control/wizard_data.json", "control"),
    asset("material_pricebook_seed.json", "."),
]

hiddenimports = [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "fitz",
    "PIL._tkinter_finder",
    "pythoncom",
    "win32com",
    "win32com.client",
]

excluded_modules = [
    "pytest",
    "tensorboard",
    "tensorflow",
    "torch",
    "torchvision",
]

a = Analysis(
    [str(ROOT / "control" / "main.py")],
    pathex=[str(ROOT), str(ROOT / "control")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IEC-site-change-manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(ROOT / "packaging" / "windows_version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="IEC-site-change-manager",
)
