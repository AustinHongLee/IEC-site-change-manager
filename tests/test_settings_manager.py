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
