# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parents[1]

hiddenimports = [
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "clr_loader",
]

excluded_modules = [
    "pytest",
    "tensorboard",
    "tensorflow",
    "torch",
    "torchvision",
]

a = Analysis(
    [str(SPEC_DIR / "pywebview_smoke_app.py")],
    pathex=[str(ROOT), str(SPEC_DIR)],
    binaries=[],
    datas=[],
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
    name="pywebview-smoke",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="pywebview-smoke",
)
