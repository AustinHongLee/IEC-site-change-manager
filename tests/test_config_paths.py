# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import config


def test_resolve_base_dir_uses_executable_folder_when_frozen(monkeypatch, tmp_path):
    exe_path = tmp_path / "IEC-site-change-manager.exe"

    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "executable", str(exe_path))

    assert config.resolve_base_dir() == str(tmp_path.resolve())
