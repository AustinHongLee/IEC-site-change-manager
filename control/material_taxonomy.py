# -*- coding: utf-8 -*-
"""Shared material taxonomy and normalization helpers."""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


TAXONOMY_SCHEMA = "material_taxonomy.v1"

_BROAD_CATEGORIES = {"", "材料", "配管", "管件", "閥件", "其他"}

_FALLBACK_TAXONOMY: dict[str, Any] = {
    "schema_version": TAXONOMY_SCHEMA,
    "version": "fallback",
    "axes": {
        "nominal_diameter": {"values": ["DN15", "DN20", "DN25", "DN40", "DN50", "DN80", "DN100"]},
        "schedule": {"values": ["SCH10", "SCH40", "SCH80", "XS", "XXS"]},
        "material_family": {
            "values": [
                {
                    "label": "白鐵系",
                    "canonical": ["SUS304", "SUS304L", "SUS316", "SUS316L", "SUS321"],
                    "aliases": ["通用白鐵", "白鐵", "不銹鋼", "不鏽鋼", "STAINLESS", "SUS", "SS"],
                },
                {
                    "label": "黑鐵系",
                    "canonical": ["A36/SS400", "A106 GR.B", "A234 GR.WPB", "A105", "CS"],
                    "aliases": ["通用黑鐵", "黑鐵", "碳鋼", "CS", "AS"],
                },
                {"label": "鍍鋅系", "canonical": ["GI", "HDG"], "aliases": ["鍍鋅", "GALV", "HDG"]},
            ]
        },
        "material_grade": {
            "values": [
                "SUS304",
                "SUS304L",
                "SUS316",
                "SUS316L",
                "SUS321",
                "A36/SS400",
                "A106 GR.B",
                "A53 GR.B",
                "A234 GR.WPB",
                "A105",
                "CS",
                "GI",
                "HDG",
            ]
        },
    },
    "categories": [
        {"label": "管材", "class": "pipe"},
        {"label": "彎頭", "class": "elbow"},
        {"label": "三通", "class": "tee"},
        {"label": "法蘭", "class": "flange"},
        {"label": "螺栓", "class": "bolt"},
        {"label": "其他", "class": "other"},
    ],
    "icons": [
        {"icon": "Pipe", "label": "管材"},
        {"icon": "Elbow", "label": "彎頭"},
        {"icon": "Tee", "label": "三通"},
        {"icon": "Flange", "label": "法蘭"},
        {"icon": "BoltNut", "label": "螺栓"},
        {"icon": "Other", "label": "其他"},
    ],
    "part_types": [
        {"code": "pipe", "label": "無縫鋼管", "category": "管材", "icon": "Pipe", "aliases": ["鋼管", "PIPE"]},
        {"code": "elbow", "label": "彎頭", "category": "彎頭", "icon": "Elbow", "aliases": ["彎頭", "ELBOW"]},
        {"code": "tee", "label": "三通", "category": "三通", "icon": "Tee", "aliases": ["三通", "TEE"]},
        {"code": "reducer", "label": "大小頭", "category": "大小頭", "icon": "Reducer", "aliases": ["大小頭", "同心大小頭", "偏心大小頭", "REDUCER"]},
        {"code": "angle_steel", "label": "角鋼", "category": "角鋼", "icon": "SteelSection", "aliases": ["ANGLE", "角鋼", "L型鋼"]},
        {"code": "steel_plate", "label": "鋼板", "category": "鋼板", "icon": "SteelPlate", "aliases": ["PLATE", "鋼板"]},
        {"code": "pipe_shoe", "label": "管鞋", "category": "管鞋", "icon": "PipeShoe", "aliases": ["PIPE SHOE", "管鞋"]},
        {"code": "pipe_clamp", "label": "管夾", "category": "管夾", "icon": "PipeClamp", "aliases": ["CLAMP", "管夾"]},
        {"code": "flange", "label": "法蘭", "category": "法蘭", "icon": "Flange", "aliases": ["法蘭", "FLANGE"]},
        {"code": "bolt", "label": "螺栓", "category": "螺栓", "icon": "BoltNut", "aliases": ["螺絲", "螺栓", "BOLT", "NUT"]},
    ],
}

_INCH_DN = {
    '1/8"': "DN6",
    '1/4"': "DN8",
    '3/8"': "DN10",
    '1/2"': "DN15",
    '3/4"': "DN20",
    '1"': "DN25",
    '1.1/4"': "DN32",
    '1-1/4"': "DN32",
    '1 1/4"': "DN32",
    '1.1/2"': "DN40",
    '1-1/2"': "DN40",
    '1 1/2"': "DN40",
    '2"': "DN50",
    '2.1/2"': "DN65",
    '2-1/2"': "DN65",
    '2 1/2"': "DN65",
    '3"': "DN80",
    '3.1/2"': "DN90",
    '3-1/2"': "DN90",
    '3 1/2"': "DN90",
    '4"': "DN100",
    '5"': "DN125",
    '6"': "DN150",
    '8"': "DN200",
    '10"': "DN250",
    '12"': "DN300",
    '14"': "DN350",
    '16"': "DN400",
    '18"': "DN450",
    '20"': "DN500",
}


def _candidate_paths(project_root: str | Path | None) -> list[Path]:
    paths: list[Path] = []
    if project_root:
        root = Path(project_root)
        paths.append(root / "records" / "material_taxonomy.json")
    try:
        from resources import resource_path

        paths.append(Path(resource_path("records", "material_taxonomy.json")))
    except Exception:
        pass
    paths.append(Path(__file__).resolve().parents[1] / "records" / "material_taxonomy.json")
    return paths


@lru_cache(maxsize=16)
def load_taxonomy(project_root: str = "") -> dict[str, Any]:
    for path in _candidate_paths(project_root):
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict) and data.get("schema_version") == TAXONOMY_SCHEMA:
                    return data
        except Exception:
            continue
    return copy.deepcopy(_FALLBACK_TAXONOMY)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _blob(value: Any) -> str:
    text = _clean(value).upper()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"[\s_\-./]+", "", text)
    return text


def _axis_values(taxonomy: dict[str, Any], axis: str) -> list[str]:
    spec = ((taxonomy.get("axes") or {}).get(axis) or {})
    values = spec.get("values") or []
    return [str(v) for v in values if isinstance(v, str)]


def _normalize_one_size(value: Any, *, bare_dn: bool = False) -> str:
    text = _clean(value)
    if not text:
        return ""
    upper = text.upper().replace("Φ", "").replace(" ", "")
    m = re.fullmatch(r"DN\s*(\d+)", upper)
    if m:
        return f"DN{int(m.group(1))}"
    m = re.fullmatch(r"(\d+)\s*A", upper)
    if m:
        return f"DN{int(m.group(1))}"
    if bare_dn and re.fullmatch(r"\d+", upper):
        return f"DN{int(upper)}"

    inch = upper.replace("INCH", '"').replace("”", '"').replace("''", '"')
    inch = inch.replace("'", '"')
    if '"' not in inch and re.search(r"\d+\s+\d+/\d+", text):
        inch += '"'
    if '"' in inch and not inch.endswith('"'):
        inch = inch.split('"', 1)[0] + '"'
    inch = inch.replace(" ", "")
    inch = inch.replace("-", "-")
    if inch in _INCH_DN:
        return _INCH_DN[inch]
    return text


def normalize_size(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    upper = text.upper().replace(" ", "")
    if (
        "依圖" in text
        or re.match(r"^[LCHM]\d", upper)
        or re.search(r"\dT\b", upper)
        or "*" in text
    ):
        return text.replace("*", "x")
    parts = re.split(r"\s*[xX×*]\s*", text)
    if len(parts) > 1:
        return "x".join(_normalize_one_size(part, bare_dn=True) for part in parts if _clean(part))
    return _normalize_one_size(text)


def normalize_schedule(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    up = text.upper().replace(" ", "").replace(".", "")
    up = up.replace("S-", "SCH").replace("SCHEDULE", "SCH")
    if up.startswith("CLASS") and re.fullmatch(r"CLASS\d{2,4}", up):
        return f"{up[5:]}#"
    if re.fullmatch(r"SCH-?\d+[A-Z]*", up):
        return up.replace("-", "")
    if re.fullmatch(r"S\d+[A-Z]*", up):
        return "SCH" + up[1:]
    if re.fullmatch(r"\d{2,4}(#|LB|LBS|CLASS)?", up):
        num = re.match(r"\d+", up).group(0)
        if up.endswith(("LB", "LBS")) or "CLASS" in up or int(num) >= 100:
            return f"{num}#"
        return f"SCH{num}"
    if up in {"STD", "XS", "XXS"}:
        return up
    m = re.search(r"(SCH\s*-?\s*\d+[A-Z]*|\d{3,4}\s*(?:#|LB|LBS)|XS|XXS|STD)", text.upper())
    if m:
        return normalize_schedule(m.group(1))
    return text


def normalize_material(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    up = text.upper().replace("　", " ")
    up = re.sub(r"\s*\.\s*$", "", up)
    up = re.sub(r"\bA(\d{2,3})\s*-\s*", r"A\1 ", up)
    up = re.sub(r"\bA106\s*[- ]?\s*B\b", "A106 GR.B", up)
    up = re.sub(r"\bA53\s*[- ]?\s*B\b", "A53 GR.B", up)
    up = re.sub(r"\bSUS\s+(\d{3}[A-Z]?)\b", r"SUS\1", up)
    up = re.sub(r"\bSS\s+(\d{3}[A-Z]?)\b", r"SS\1", up)
    compact = re.sub(r"[^A-Z0-9]", "", up)
    m = re.fullmatch(r"(?:SUS|SS)?(304L?|316L?|321)", compact)
    if m:
        return f"SUS{m.group(1)}"
    return " ".join(up.split())


def material_family(value: Any, taxonomy: dict[str, Any] | None = None) -> str:
    tax = taxonomy or load_taxonomy("")
    mat = normalize_material(value)
    blob = _blob(mat)
    families = (((tax.get("axes") or {}).get("material_family") or {}).get("values") or [])
    for fam in families:
        labels = [fam.get("label"), *(fam.get("canonical") or []), *(fam.get("aliases") or [])]
        for label in labels:
            needle = _blob(label)
            if not needle:
                continue
            if len(needle) <= 2 and blob != needle:
                continue
            if needle == blob or needle in blob:
                return str(fam.get("label") or "")
    return ""


def classify_part_type(value: Any, taxonomy: dict[str, Any] | None = None) -> dict[str, Any]:
    tax = taxonomy or load_taxonomy("")
    source = _blob(value)
    if not source:
        return {}
    candidates = tax.get("part_types") or []
    for item in candidates:
        labels = [item.get("label"), item.get("code"), *(item.get("aliases") or [])]
        for label in labels:
            needle = _blob(label)
            if needle and needle in source:
                return item
    return {}


def category_for_part(value: Any, taxonomy: dict[str, Any] | None = None) -> str:
    part = classify_part_type(value, taxonomy)
    return str(part.get("category") or "其他")


def icon_for_part(value: Any, taxonomy: dict[str, Any] | None = None) -> str:
    part = classify_part_type(value, taxonomy)
    return str(part.get("icon") or "Other")


def enrich_material_item(item: dict[str, Any], taxonomy: dict[str, Any] | None = None) -> dict[str, Any]:
    tax = taxonomy or load_taxonomy("")
    out = dict(item)
    part = _clean(out.get("零件類型") or out.get("part"))
    spec = _clean(out.get("規格") or out.get("spec") or "")
    typed = classify_part_type(f"{part} {spec}", tax)
    inferred_cat = str(typed.get("category") or category_for_part(part, tax) or "其他")
    current_cat = _clean(out.get("類別") or out.get("cat"))
    out["零件類型"] = part
    out["尺寸"] = normalize_size(out.get("尺寸") or out.get("size"))
    out["SCH"] = normalize_schedule(out.get("SCH") or out.get("sch") or out.get("schedule"))
    out["材質"] = normalize_material(out.get("材質") or out.get("mat") or out.get("material"))
    out["類別"] = inferred_cat if current_cat in _BROAD_CATEGORIES else current_cat
    out["單位"] = _clean(out.get("單位") or out.get("unit") or typed.get("unit"))
    out["icon"] = str(out.get("icon") or typed.get("icon") or icon_for_part(part, tax) or "Other")
    out["material_family"] = material_family(out["材質"], tax)
    out["match_key"] = material_match_key(out, tax)
    return out


def material_match_key(item: dict[str, Any], taxonomy: dict[str, Any] | None = None) -> str:
    part = _clean(item.get("零件類型") or item.get("part")).casefold()
    size = normalize_size(item.get("尺寸") or item.get("size")).casefold()
    sch = normalize_schedule(item.get("SCH") or item.get("sch") or item.get("schedule")).casefold()
    mat = normalize_material(item.get("材質") or item.get("mat") or item.get("material")).casefold()
    return f"{part}|{size}|{sch}|{mat}"


def taxonomy_options(taxonomy: dict[str, Any] | None = None) -> dict[str, list[str]]:
    tax = taxonomy or load_taxonomy("")
    cats = [str(c.get("label")) for c in (tax.get("categories") or []) if c.get("label")]
    parts = [str(p.get("label")) for p in (tax.get("part_types") or []) if p.get("label")]
    mats = []
    for fam in (((tax.get("axes") or {}).get("material_family") or {}).get("values") or []):
        mats.append(str(fam.get("label") or ""))
        mats.extend(str(x) for x in (fam.get("canonical") or []))
    mats.extend(_axis_values(tax, "material_grade"))
    return {
        "cat": [x for x in cats if x],
        "part": [x for x in parts if x],
        "size": _axis_values(tax, "nominal_diameter"),
        "sch": _axis_values(tax, "schedule") + _axis_values(tax, "rating"),
        "mat": list(dict.fromkeys(x for x in mats if x)),
    }


__all__ = [
    "TAXONOMY_SCHEMA",
    "category_for_part",
    "classify_part_type",
    "enrich_material_item",
    "icon_for_part",
    "load_taxonomy",
    "material_family",
    "material_match_key",
    "normalize_material",
    "normalize_schedule",
    "normalize_size",
    "taxonomy_options",
]
