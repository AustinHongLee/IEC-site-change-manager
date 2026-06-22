# -*- coding: utf-8 -*-

import os
import subprocess
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import app_info


def test_app_info_formats_shared_identity():
    assert app_info.APP_ID == "iec-site-change-manager"
    assert app_info.APP_VERSION
    assert "IEC Site Change Manager" in app_info.format_app_identity()
    assert app_info.APP_VERSION in app_info.format_window_title()


def test_main_version_cli_exits_before_startup_guard():
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    result = subprocess.run(
        [sys.executable, os.path.join(repo, "control", "main.py"), "--version"],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "IEC Site Change Manager" in result.stdout
    assert app_info.APP_VERSION in result.stdout


def test_health_check_prints_app_identity():
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    result = subprocess.run(
        [sys.executable, os.path.join(repo, "control", "main.py"), "--health-check"],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert app_info.format_app_identity() in result.stdout
