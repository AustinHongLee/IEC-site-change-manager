# -*- coding: utf-8 -*-

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))

from app_info import APP_VERSION


def test_pyinstaller_spec_tracks_required_entrypoint_and_assets():
    repo = Path(__file__).resolve().parents[1]
    spec = (repo / "packaging" / "IEC-site-change-manager.spec").read_text(encoding="utf-8")

    assert "ROOT = Path(SPECPATH).resolve().parent" in spec
    assert 'control" / "main.py"' in spec
    assert 'asset("packaging/generated/build_info.json", ".")' in spec
    assert 'asset("template", "template")' in spec
    assert 'asset("control/image", "control/image")' in spec
    assert 'asset("control/wizard_data.json", "control")' in spec
    assert 'excluded_modules = [' in spec
    assert '"pytest"' in spec
    assert '"torch"' in spec
    assert '"torchvision"' in spec
    assert 'contents_directory="."' not in spec
    assert 'console=True' in spec
    assert 'version=str(ROOT / "packaging" / "windows_version_info.txt")' in spec


def test_gitignore_excludes_pyinstaller_outputs():
    repo = Path(__file__).resolve().parents[1]
    ignore = (repo / ".gitignore").read_text(encoding="utf-8")

    assert "\nbuild/\n" in ignore
    assert "\ndist/\n" in ignore
    assert "\npackaging/generated/\n" in ignore


def test_windows_version_info_tracks_app_version():
    repo = Path(__file__).resolve().parents[1]
    version_info = (repo / "packaging" / "windows_version_info.txt").read_text(encoding="utf-8")

    assert "FileDescription', 'IEC Site Change Manager" in version_info
    assert "ProductName', 'IEC Site Change Manager" in version_info
    assert f"FileVersion', '{APP_VERSION}" in version_info
    assert f"ProductVersion', '{APP_VERSION}" in version_info
