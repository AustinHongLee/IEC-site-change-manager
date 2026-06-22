# -*- coding: utf-8 -*-
"""
material_constants.py - 材料受控詞彙與 alias 正規化

權威來源先沿用 control/wizard_data.json。價目表、配價與驗證工具都應該
往這裡收斂，避免「白鐵」/「SS」和完整詞彙之間配不到價。
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any

from resources import resource_path

WIZARD_DATA_PATH = resource_path("control", "wizard_data.json")

MATERIAL_FIELD_COMPONENT = "零件類型"
MATERIAL_FIELD_SIZE = "尺寸"
MATERIAL_FIELD_SCH = "SCH"
MATERIAL_FIELD_MATERIAL = "材質"

MATERIAL_ALIASES = {
    "白鐵": "白鐵 (Stainless Steel)",
    "白鐵(stainlesssteel)": "白鐵 (Stainless Steel)",
    "ss": "白鐵 (Stainless Steel)",
    "s/s": "白鐵 (Stainless Steel)",
    "stainless": "白鐵 (Stainless Steel)",
    "stainlesssteel": "白鐵 (Stainless Steel)",
    "不鏽鋼": "白鐵 (Stainless Steel)",
    "不銹鋼": "白鐵 (Stainless Steel)",
    "黑鐵": "黑鐵 (Carbon Steel)",
    "黑鐵(carbonsteel)": "黑鐵 (Carbon Steel)",
    "cs": "黑鐵 (Carbon Steel)",
    "c/s": "黑鐵 (Carbon Steel)",
    "carbon": "黑鐵 (Carbon Steel)",
    "carbonsteel": "黑鐵 (Carbon Steel)",
    "碳鋼": "黑鐵 (Carbon Steel)",
}

DEFAULT_UNIT_BY_COMPONENT = {
    "Pipe (管)": "M",
    "Elbow (彎頭)": "個",
    "Tee (三通)": "個",
    "Reducer (大小頭)": "個",
    "Cap (封蓋)": "個",
    "Coupling (接頭)": "個",
    "Union (活接)": "個",
    "Cross (四通)": "個",
    "Bushing (異徑接頭)": "個",
    "Nipple (短管)": "個",
    "Plug (管塞)": "個",
    "Olet (支管座)": "個",
    "Flange (法蘭)": "個",
    "Valve (閥)": "個",
    "Control Valve (控制閥)": "個",
    "Strainer (過濾器)": "個",
    "Steam Trap (疏水器)": "個",
    "Sight Glass (視鏡)": "個",
    "Flowmeter (流量計)": "個",
    "Gasket (墊片)": "片",
    "Bolt & Nut (螺栓螺帽)": "組",
    "Welding Electrode (焊條)": "kg",
    "Filler Wire (焊線)": "kg",
    "Thread Seal Tape (止洩帶)": "卷",
}


@dataclass(frozen=True)
class MaterialConstants:
    components: tuple[str, ...]
    materials: tuple[str, ...]
    sizes: tuple[str, ...]
    schedules: tuple[str, ...]

    def normalized_map(self, field: str) -> dict[str, str]:
        values = {
            MATERIAL_FIELD_COMPONENT: self.components,
            MATERIAL_FIELD_MATERIAL: self.materials,
            MATERIAL_FIELD_SIZE: self.sizes,
            MATERIAL_FIELD_SCH: self.schedules,
        }.get(field, ())
        return {normalize_material_key(value): value for value in values}


_CACHE: MaterialConstants | None = None


def normalize_material_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("，", ",")
    return re.sub(r"\s+", "", text)


def load_material_constants(path: str | None = None) -> MaterialConstants:
    global _CACHE
    path = path or WIZARD_DATA_PATH
    if path == WIZARD_DATA_PATH and _CACHE is not None:
        return _CACHE

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    materials = data.get("materials", {}) if isinstance(data, dict) else {}
    constants = MaterialConstants(
        components=tuple(str(item.get("name", "")).strip() for item in materials.get("components", []) if item.get("name")),
        materials=tuple(str(item.get("name", "")).strip() for item in materials.get("pipe_types", []) if item.get("name")),
        sizes=tuple(str(value).strip() for value in materials.get("sizes_inch", []) if str(value).strip()),
        schedules=tuple(str(value).strip() for value in materials.get("schedules", []) if str(value).strip()),
    )
    if path == WIZARD_DATA_PATH:
        _CACHE = constants
    return constants


def material_default_unit(component: Any) -> str:
    canonical = canonicalize_material_value(MATERIAL_FIELD_COMPONENT, component)
    return DEFAULT_UNIT_BY_COMPONENT.get(canonical, "個" if canonical else "")


def canonicalize_material_value(field: str, value: Any, *, constants: MaterialConstants | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    constants = constants or load_material_constants()
    norm = normalize_material_key(text)

    if field == MATERIAL_FIELD_MATERIAL:
        alias = MATERIAL_ALIASES.get(norm)
        if alias:
            return alias

    canonical = constants.normalized_map(field).get(norm)
    return canonical or text


def canonicalize_material_row(row: dict[str, Any], *, constants: MaterialConstants | None = None) -> dict[str, Any]:
    constants = constants or load_material_constants()
    out = copy.deepcopy(row)
    for field in (
        MATERIAL_FIELD_COMPONENT,
        MATERIAL_FIELD_SIZE,
        MATERIAL_FIELD_SCH,
        MATERIAL_FIELD_MATERIAL,
    ):
        if field in out:
            out[field] = canonicalize_material_value(field, out.get(field), constants=constants)
    return out


def is_controlled_material_value(field: str, value: Any, *, allow_empty: bool = False) -> bool:
    text = str(value or "").strip()
    if not text:
        return allow_empty
    constants = load_material_constants()
    canonical = canonicalize_material_value(field, text, constants=constants)
    return normalize_material_key(canonical) in constants.normalized_map(field)
