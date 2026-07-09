# -*- coding: utf-8 -*-

from pathlib import Path


def test_pywebview_spike_declares_probe_app_spec_and_runbook():
    repo = Path(__file__).resolve().parents[1]
    app = (repo / "packaging" / "spike" / "pywebview_smoke_app.py").read_text(encoding="utf-8")
    spec = (repo / "packaging" / "spike" / "pywebview_smoke.spec").read_text(encoding="utf-8")
    readme = (repo / "packaging" / "spike" / "README.md").read_text(encoding="utf-8")

    assert "class SmokeApi" in app
    assert "def ping" in app
    assert "--health-check" in app
    assert "pywebviewready" in app
    assert "webview.create_window" in app

    assert 'name="pywebview-smoke"' in spec
    assert '"webview.platforms.winforms"' in spec
    assert '"webview.platforms.edgechromium"' in spec
    assert '"clr_loader"' in spec
    assert 'console=True' in spec

    assert "python -m PyInstaller --noconfirm --clean packaging\\spike\\pywebview_smoke.spec" in readme
    assert "dist\\pywebview-smoke\\pywebview-smoke.exe --health-check" in readme


def test_runtime_requirements_include_webview_packaging_dependencies():
    repo = Path(__file__).resolve().parents[1]
    requirements = (repo / "requirements.txt").read_text(encoding="utf-8")

    assert "pywebview" in requirements
    assert "PyInstaller" in requirements
