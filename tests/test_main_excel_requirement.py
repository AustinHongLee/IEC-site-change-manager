# -*- coding: utf-8 -*-

import os
import sys
from types import SimpleNamespace

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import main as app_main
from capabilities import CapabilityResult, format_mandatory_excel_unavailable


def _args(**overrides):
    data = {
        "cli": True,
        "date": None,
        "retry": False,
        "health_check": False,
        "audit_integrity": False,
        "diagnostics": False,
        "diagnostics_probe": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_support_commands_do_not_require_excel_runtime():
    assert app_main._requires_excel_runtime(_args(health_check=True)) is False
    assert app_main._requires_excel_runtime(_args(audit_integrity=True)) is False
    assert app_main._requires_excel_runtime(_args(diagnostics=True)) is False
    assert app_main._requires_excel_runtime(_args(diagnostics_probe=True)) is False
    assert app_main._requires_excel_runtime(_args()) is True


def test_mandatory_excel_message_blocks_normal_runtime(monkeypatch, capsys):
    import capabilities

    monkeypatch.setattr(
        capabilities,
        "detect_excel_com",
        lambda: CapabilityResult("excel_com", False, reason="無法啟動 Excel COM", detail="missing Excel"),
    )

    with pytest.raises(SystemExit) as exc:
        app_main._enforce_excel_requirement(_args())

    assert exc.value.code == 4
    output = capsys.readouterr().out
    assert "此電腦不符合公司使用條件" in output
    assert "沒有 Excel 的電腦不允許使用此軟體" in output


def test_mandatory_excel_formatter_does_not_offer_non_com_usage():
    text = format_mandatory_excel_unavailable(
        CapabilityResult("excel_com", False, reason="缺少 Microsoft Excel")
    )

    assert "不允許使用此軟體" in text
    assert "你仍可使用" not in text
