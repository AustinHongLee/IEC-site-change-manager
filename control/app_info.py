# -*- coding: utf-8 -*-
"""Application identity shared by CLI, GUI, and release diagnostics."""

APP_ID = "iec-site-change-manager"
APP_NAME = "IEC Site Change Manager"
APP_LOCAL_NAME = "工務修改單"
APP_VERSION = "0.1.0-alpha"
APP_CHANNEL = "internal"


def format_app_identity() -> str:
    return f"{APP_NAME} ({APP_LOCAL_NAME}) {APP_VERSION} [{APP_CHANNEL}]"


def format_version_cli() -> str:
    return f"{APP_NAME} {APP_VERSION} ({APP_CHANNEL})"


def format_window_title() -> str:
    return f"{APP_LOCAL_NAME} - {APP_NAME} {APP_VERSION}"
