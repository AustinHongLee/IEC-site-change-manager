# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import config
import resources


def test_resolve_base_dir_uses_executable_folder_when_frozen(monkeypatch, tmp_path):
    exe_path = tmp_path / "IEC-site-change-manager.exe"

    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "executable", str(exe_path))

    assert config.resolve_base_dir() == str(tmp_path.resolve())


def test_resource_dir_uses_meipass_when_frozen(monkeypatch, tmp_path):
    internal = tmp_path / "_internal"
    internal.mkdir()

    monkeypatch.setattr(resources.sys, "frozen", True, raising=False)
    monkeypatch.setattr(resources.sys, "_MEIPASS", str(internal), raising=False)

    assert resources.resolve_resource_dir() == str(internal.resolve())
    assert resources.resource_path("template", "template_file.xlsm") == str(
        internal / "template" / "template_file.xlsm"
    )


def test_project_path_stays_on_exe_folder_when_resources_are_internal(monkeypatch, tmp_path):
    internal = tmp_path / "_internal"
    internal.mkdir()
    exe_path = tmp_path / "IEC-site-change-manager.exe"

    monkeypatch.setattr(resources.sys, "frozen", True, raising=False)
    monkeypatch.setattr(resources.sys, "executable", str(exe_path), raising=False)
    monkeypatch.setattr(resources.sys, "_MEIPASS", str(internal), raising=False)

    assert resources.project_path("records", "material_pricebook.json") == str(
        tmp_path / "records" / "material_pricebook.json"
    )
    assert resources.resource_path("material_pricebook_seed.json") == str(
        internal / "material_pricebook_seed.json"
    )
