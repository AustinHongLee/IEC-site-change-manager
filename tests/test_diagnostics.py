# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import diagnostics as diagnostics_module
from diagnostics import _collect_log_excerpts, collect_support_bundle


def test_collect_support_bundle_writes_zip_with_json_and_health_text(tmp_path):
    output = tmp_path / "out"

    result = collect_support_bundle(
        tmp_path,
        output_dir=output,
        timestamp=datetime(2026, 6, 22, 12, 0, 0),
    )

    assert result["ok"] is True
    assert result["startup_action"] == "initialize"
    bundle_path = result["bundle_path"]
    assert bundle_path.endswith("support_bundle_20260622_120000.zip")
    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        assert names == {"diagnostics.json", "health_check.txt"}
        diagnostics = json.loads(bundle.read("diagnostics.json").decode("utf-8"))
        health = bundle.read("health_check.txt").decode("utf-8")

    assert diagnostics["schema_version"] == "support_bundle.v1"
    assert diagnostics["app"]["version"]
    assert diagnostics["app"]["paths"]["template_6_exists"] is True
    assert diagnostics["app"]["paths"]["wizard_data_exists"] is True
    assert diagnostics["project"]["startup"]["decision"]["action"] == "initialize"
    assert "IEC Site Change Manager" in health


def test_main_diagnostics_cli_creates_bundle(tmp_path):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    output = tmp_path / "diag"

    result = subprocess.run(
        [
            sys.executable,
            os.path.join(repo, "control", "main.py"),
            "--diagnostics",
            "--diagnostics-output",
            str(output),
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "支援診斷包:" in result.stdout
    assert list(output.glob("support_bundle_*.zip"))


def test_collect_support_bundle_includes_recent_logs(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "app.log").write_text("RC0 smoke 測試訊息\n", encoding="utf-8")
    output = tmp_path / "out"

    result = collect_support_bundle(
        tmp_path,
        output_dir=output,
        timestamp=datetime(2026, 6, 22, 12, 0, 0),
    )

    assert result["logs_included"] == 1
    with zipfile.ZipFile(result["bundle_path"]) as bundle:
        names = set(bundle.namelist())
        assert "logs/app.log" in names
        assert "RC0 smoke 測試訊息" in bundle.read("logs/app.log").decode("utf-8")


def test_collect_support_bundle_can_enable_output_probes(tmp_path, monkeypatch):
    captured = {}

    def fake_capability_report(*, probe_com_application, probe_libreoffice_version):
        captured["probe_com_application"] = probe_com_application
        captured["probe_libreoffice_version"] = probe_libreoffice_version
        return {"ok": True, "capabilities": []}

    monkeypatch.setattr(diagnostics_module, "build_output_capability_report", fake_capability_report)

    result = collect_support_bundle(
        tmp_path,
        output_dir=tmp_path / "out",
        timestamp=datetime(2026, 6, 22, 12, 0, 0),
        probe_com_application=True,
        probe_libreoffice_version=True,
    )

    assert captured == {
        "probe_com_application": True,
        "probe_libreoffice_version": True,
    }
    with zipfile.ZipFile(result["bundle_path"]) as bundle:
        diagnostics = json.loads(bundle.read("diagnostics.json").decode("utf-8"))
    assert diagnostics["probe"] == {
        "com_application": True,
        "libreoffice_version": True,
    }


def test_collect_log_excerpts_limits_to_newest_files_and_tails_large_logs(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    samples = [
        ("old.log", "old", 1000),
        ("third.log", "third", 2000),
        ("newer.log", "newer", 3000),
        ("newest.log", "prefix-1234567890", 4000),
    ]
    for name, content, mtime in samples:
        path = logs_dir / name
        path.write_text(content, encoding="utf-8")
        os.utime(path, (mtime, mtime))

    excerpts = _collect_log_excerpts(tmp_path, max_files=2, max_bytes=6)

    assert [arcname for arcname, _ in excerpts] == ["logs/newest.log", "logs/newer.log"]
    newest_text = excerpts[0][1]
    assert newest_text.startswith("（已截斷")
    assert newest_text.endswith("567890")
    assert "prefix" not in newest_text
