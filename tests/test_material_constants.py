# -*- coding: utf-8 -*-
"""material_constants.py 單元測試"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from material_constants import (
    MATERIAL_FIELD_COMPONENT,
    MATERIAL_FIELD_MATERIAL,
    canonicalize_material_value,
    is_controlled_material_value,
    load_material_constants,
    material_default_unit,
)


def test_load_material_constants_from_wizard_data():
    constants = load_material_constants()

    assert "Pipe (管)" in constants.components
    assert "白鐵 (Stainless Steel)" in constants.materials
    assert '2"' in constants.sizes
    assert "SCH 40" in constants.schedules


def test_material_aliases_canonicalize_to_controlled_vocab():
    assert canonicalize_material_value(MATERIAL_FIELD_MATERIAL, "SS") == "白鐵 (Stainless Steel)"
    assert canonicalize_material_value(MATERIAL_FIELD_MATERIAL, "白鐵") == "白鐵 (Stainless Steel)"
    assert canonicalize_material_value(MATERIAL_FIELD_MATERIAL, "CS") == "黑鐵 (Carbon Steel)"
    assert is_controlled_material_value(MATERIAL_FIELD_MATERIAL, "SS") is True


def test_unknown_values_are_preserved_for_manual_review():
    assert canonicalize_material_value(MATERIAL_FIELD_COMPONENT, "Pipe") == "Pipe"
    assert is_controlled_material_value(MATERIAL_FIELD_COMPONENT, "Pipe") is False


def test_default_units_follow_component_vocab():
    assert material_default_unit("Pipe (管)") == "M"
    assert material_default_unit("Gasket (墊片)") == "片"
    assert material_default_unit("Other (其他)") == "個"
