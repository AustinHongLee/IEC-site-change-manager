# -*- coding: utf-8 -*-

import importlib.util
from pathlib import Path


def _load_validator():
    path = Path(__file__).resolve().parents[1] / "tools" / "validate_pricebook.py"
    spec = importlib.util.spec_from_file_location("validate_pricebook_tool", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_validator_allows_same_material_with_different_sch():
    validator = _load_validator()
    vocab = validator.load_controlled_vocab()
    items = [
        {
            "id": "Pipe (管)|2\"|SCH 40|白鐵 (Stainless Steel)",
            "零件類型": "Pipe (管)",
            "尺寸": "2\"",
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "單位": "M",
            "單價": "",
            "備註": "",
        },
        {
            "id": "Pipe (管)|2\"|SCH 80|白鐵 (Stainless Steel)",
            "零件類型": "Pipe (管)",
            "尺寸": "2\"",
            "SCH": "SCH 80",
            "材質": "白鐵 (Stainless Steel)",
            "單位": "M",
            "單價": "",
            "備註": "",
        },
    ]

    report = validator.validate(items, vocab, allow_price=False)

    assert report.errors == []
    assert report.warnings == []


def test_validator_flags_alias_but_keeps_it_non_blocking():
    validator = _load_validator()
    vocab = validator.load_controlled_vocab()
    items = [
        {
            "id": "Pipe (管)|2\"|SCH 40|SS",
            "零件類型": "Pipe (管)",
            "尺寸": "2\"",
            "SCH": "SCH 40",
            "材質": "SS",
            "單位": "M",
            "單價": "",
            "備註": "",
        },
    ]

    report = validator.validate(items, vocab, allow_price=False)

    assert report.errors == []
    assert len(report.warnings) == 1
    assert "白鐵 (Stainless Steel)" in report.warnings[0]
