# -*- coding: utf-8 -*-

import logging
import sys


sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), __import__("os").pardir, "control"))

import log_config  # noqa: E402


def test_install_excepthook_logs_unhandled_exception(monkeypatch):
    records = []

    class FakeLogger:
        def critical(self, message, *args, **kwargs):
            records.append((message, kwargs))

    original = sys.excepthook
    monkeypatch.setattr(log_config, "_excepthook_installed", False)
    monkeypatch.setattr(log_config, "_previous_excepthook", None)

    hook = log_config.install_excepthook(FakeLogger(), chain=False)
    try:
        exc = RuntimeError("boom")
        hook(RuntimeError, exc, exc.__traceback__)
    finally:
        sys.excepthook = original
        log_config._excepthook_installed = False
        log_config._previous_excepthook = None

    assert records
    assert records[0][0] == "Unhandled exception"
    assert records[0][1]["exc_info"][0] is RuntimeError


def test_install_excepthook_is_idempotent(monkeypatch):
    original = sys.excepthook
    logger = logging.getLogger("test_install_excepthook_is_idempotent")
    monkeypatch.setattr(log_config, "_excepthook_installed", False)
    monkeypatch.setattr(log_config, "_previous_excepthook", None)

    first = log_config.install_excepthook(logger, chain=False)
    second = log_config.install_excepthook(logger, chain=False)
    try:
        assert first is second
    finally:
        sys.excepthook = original
        log_config._excepthook_installed = False
        log_config._previous_excepthook = None
