# -*- coding: utf-8 -*-

import json
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import settings_manager


def test_settings_manager_merges_and_saves_soffice_path(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"paths": {}}), encoding="utf-8")
    monkeypatch.setattr(settings_manager, "_get_settings_path", lambda: str(settings_path))
    settings_manager.SettingsManager._instance = None
    settings_manager._settings_manager = None

    try:
        assert settings_manager.get_soffice_path() == ""
        settings_manager.set_soffice_path("C:/LibreOffice/program/soffice.exe")

        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["paths"]["soffice_path"] == "C:/LibreOffice/program/soffice.exe"
    finally:
        settings_manager.SettingsManager._instance = None
        settings_manager._settings_manager = None


def test_settings_manager_creates_instance_from_template(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    template_path = tmp_path / "settings.template.json"
    template_path.write_text(json.dumps({
        "project": {"name": ""},
        "paths": {"drawing_list": "template-dwg.xlsx"},
        "meta": {"version": "1.3"},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(settings_manager, "_get_settings_path", lambda: str(settings_path))
    monkeypatch.setattr(settings_manager, "_get_template_path", lambda: str(template_path))
    settings_manager.SettingsManager._instance = None
    settings_manager._settings_manager = None

    try:
        sm = settings_manager.get_settings()

        assert settings_path.exists()
        assert sm.get_path("drawing_list") == "template-dwg.xlsx"
        saved = json.loads(settings_path.read_text(encoding="utf-8"))
        assert saved["paths"]["drawing_list"] == "template-dwg.xlsx"
        assert saved["paths"]["weld_control_table"] == ""
    finally:
        settings_manager.SettingsManager._instance = None
        settings_manager._settings_manager = None
