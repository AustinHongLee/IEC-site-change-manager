# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path(SPECPATH).resolve().parent
BUILD_INFO = ROOT / "packaging" / "generated" / "build_info.json"

if not BUILD_INFO.is_file():
    BUILD_INFO.parent.mkdir(parents=True, exist_ok=True)
    BUILD_INFO.write_text(
        '{\n'
        '  "schema_version": "build_info.v1",\n'
        '  "app_version": "UNKNOWN",\n'
        '  "git_commit": "UNKNOWN",\n'
        '  "built_at": "UNKNOWN",\n'
        '  "source_dirty": true\n'
        '}\n',
        encoding="utf-8",
    )


def asset(src: str, dest: str):
    return (str(ROOT / src), dest)


datas = [
    asset("packaging/generated/build_info.json", "."),
    asset("settings.template.json", "."),
    asset("template", "template"),
    asset("control/image", "control/image"),
    asset("control/wizard_data.json", "control"),
    asset("control/co_main_web", "control/co_main_web"),
    asset("control/co_wizard_web", "control/co_wizard_web"),
    asset("records/material_taxonomy.json", "records"),
    asset("records/material_catalog_rules.json", "records"),
    asset("records/seed/material_pricebook_seed.json", "records/seed"),
]

hiddenimports = [
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "clr_loader",
    "fitz",
    "PIL._tkinter_finder",
    "pythoncom",
    "win32com",
    "win32com.client",
]

excluded_modules = [
    "pytest",
    "PyQt6",
    "tensorboard",
    "tensorflow",
    "torch",
    "torchvision",
]

a = Analysis(
    [str(ROOT / "control" / "co_main_app.py")],
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
