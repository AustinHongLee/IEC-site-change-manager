# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from gui_settings import SettingsPanel


def test_settings_panel_formats_output_capability_report():
    text = SettingsPanel._format_output_capability_report({
        "summary": {"available": 2, "total": 4, "attention": 1, "blocking": 0},
        "capabilities": [
            {"label": "現場統計單 Excel", "available": True, "optional": False, "reason": "ready"},
            {"label": "非 COM PDF", "available": False, "optional": True, "reason": "missing"},
        ],
        "recommendations": ["請設定 soffice.exe"],
    })

    assert "可用 2 / 4" in text
    assert "需注意 1，阻擋 0" in text
    assert "現場統計單 Excel：可用" in text
    assert "非 COM PDF：不可用（選用）" in text
    assert "請設定 soffice.exe" in text
