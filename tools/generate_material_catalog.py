# -*- coding: utf-8 -*-
"""Generate a clean, taxonomy-driven material master catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTROL_DIR = ROOT / "control"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from material_taxonomy import load_taxonomy  # noqa: E402


MATERIALS = [
    ("通用白鐵", "SS"),
    ("通用黑鐵", "CS"),
    ("鍍鋅", "GI"),
]
GASKET_MATERIALS = [
    ("PTFE", "PTFE"),
    ("石墨", "GRAPH"),
    ("金屬纏繞", "SWG"),
    ("橡膠", "RUB"),
]
BOLT_MATERIALS = [
    ("通用白鐵", "SS"),
    ("通用黑鐵", "CS"),
    ("鍍鋅", "GI"),
]

SCHEDULES = ["SCH10", "SCH40", "SCH80", "XS", "XXS"]
FLANGE_RATINGS = ["150#", "300#", "600#"]
VALVE_RATINGS = ["150#", "300#", "600#", "800#"]
SUPPORT_MATERIALS = [
    ("A36/SS400", "AS"),
    ("通用白鐵", "SS"),
    ("鍍鋅", "GI"),
]
STEEL_SECTION_SPECS = {
    "ANG": ("角鋼", "角鋼", "SteelSection", [
        "L40*40*5", "L50*50*6", "L65*65*6", "L75*75*9", "L80*80*8", "L90*90*9",
        "L100*100*10", "L110*110*10", "L120*120*11", "L130*130*12", "L140*140*13",
        "L150*150*14", "L160*160*15", "L180*180*16",
    ]),
    "CH": ("槽鋼", "槽鋼", "SteelSection", [
        "C100*50*5", "C125*65*6", "C150*75*9", "C180*75*7", "C200*80*7.5",
        "C200*90*8", "C250*90*8", "C300*100*8.5", "C350*100*9",
        "C400*150*10", "C450*150*11", "C500*200*12",
    ]),
    "HB": ("H型鋼", "H型鋼", "SteelSection", [
        "H100*100*6", "H125*125*6.5", "H150*150*7", "H150*150*10", "H194*150*6",
        "H200*100*5.5", "H200*200*8", "H250*125*6", "H250*250*9",
        "H300*150*6.5", "H350*175*7", "H400*200*8", "H450*200*9",
        "H500*250*10", "H550*300*11", "H600*300*12",
    ]),
}
PLATE_STOCK_SIZES = ["1219x2438", "1524x3048"]
PLATE_THICKNESSES = ["3t", "4.5t", "6t", "9t", "12t", "16t", "19t", "22t", "25t", "32t"]
PIPE_SHOE_PARTS = [
    ("PSHOE-STD", "標準管鞋"),
    ("PSHOE-GUIDE", "導向管鞋"),
    ("PSHOE-ANCHOR", "固定管鞋"),
]
PIPE_CLAMP_PARTS = [
    ("PCLAMP-U", "U型管夾"),
    ("PCLAMP-TWOHOLE", "雙孔管夾"),
    ("PCLAMP-ELEC", "電工管夾"),
    ("PCLAMP-HEAVY", "重型管束"),
]
PIPE_SUPPORT_PARTS = [
    ("PSTOOL", "管托", "管托", "PipeShoe", "個"),
    ("SLIDE", "滑板", "滑板", "SlidePlate", "片"),
]
BASE_PLATE_SIZES = [
    "100x100x6t",
    "150x150x9t",
    "200x200x12t",
    "250x250x16t",
    "300x300x19t",
    "350x350x25t",
]
SLIDE_PLATE_SIZES = [
    "100x100x3t",
    "150x150x3t",
    "200x200x3t",
    "250x250x5t",
]


def _axis(taxonomy: dict[str, Any], key: str) -> list[str]:
    return [str(v) for v in (((taxonomy.get("axes") or {}).get(key) or {}).get("values") or []) if isinstance(v, str)]


def _code(value: str) -> str:
    text = (
        value.upper()
        .replace("SCH", "S")
        .replace("#", "")
        .replace("通用", "")
        .replace("白鐵", "SS")
        .replace("黑鐵", "CS")
        .replace("鍍鋅", "GI")
        .replace("金屬纏繞", "SWG")
        .replace("石墨", "GRAPH")
        .replace("橡膠", "RUB")
        .replace("A36/SS400", "AS")
        .replace("*", "X")
        .replace("/", "")
        .replace(".", "P")
        .replace(" ", "")
    )
    return text or "GEN"


def _rating_code(value: str) -> str:
    return "CL" + value.replace("#", "")


def _dn_number(size: str) -> int:
    text = str(size).upper().replace("DN", "")
    try:
        return int(text)
    except ValueError:
        return 0


def _dual_size_pairs(dns: list[str], *, max_step: int = 4) -> list[tuple[str, str]]:
    """Return practical reducing pairs: larger DN first, smaller branch/outlet second."""
    pairs: list[tuple[str, str]] = []
    ordered = sorted(dns, key=_dn_number)
    for i, larger in enumerate(ordered):
        for smaller in ordered[max(0, i - max_step):i]:
            pairs.append((larger, smaller))
    return pairs


def _olet_pairs(dns: list[str]) -> list[tuple[str, str]]:
    """Header x branch pairs for Olet. Keep common branch sizes broad without full Cartesian bloat."""
    ordered = sorted(dns, key=_dn_number)
    common_branches = {15, 20, 25, 40, 50, 80, 100, 150}
    pairs: list[tuple[str, str]] = []
    for header in ordered:
        header_dn = _dn_number(header)
        for branch in ordered:
            branch_dn = _dn_number(branch)
            if branch_dn >= header_dn:
                continue
            if branch_dn in common_branches or branch_dn >= header_dn // 2:
                pairs.append((header, branch))
    return pairs


def _item(prefix: str, part: str, category: str, size: str, sch: str, mat: str, mat_code: str, unit: str) -> dict:
    spec_code = _rating_code(sch) if sch.endswith("#") else _code(sch)
    return {
        "id": f"{prefix}-{_code(size)}-{spec_code}-{mat_code}",
        "零件類型": part,
        "尺寸": size,
        "SCH": sch,
        "材質": mat,
        "類別": category,
        "單位": unit,
        "規格": f"{part},{size},{sch},{mat}",
        "來源": "標準總庫",
        "備註": "",
    }


def _dual_item(
    prefix: str,
    part: str,
    category: str,
    primary: str,
    secondary: str,
    sch: str,
    mat: str,
    mat_code: str,
    unit: str,
    primary_label: str = "主尺寸",
    secondary_label: str = "分支尺寸",
) -> dict:
    size = f"{primary}x{secondary}"
    row = _item(prefix, part, category, size, sch, mat, mat_code, unit)
    row["規格"] = f"{part},{primary_label}:{primary},{secondary_label}:{secondary},{sch},{mat}"
    row[primary_label] = primary
    row[secondary_label] = secondary
    return row


def _bolt_item(prefix: str, part: str, category: str, dia: str, length: str, mat: str, mat_code: str, unit: str) -> dict:
    size = dia if not length else f"{dia}x{length.replace('L', '')}"
    spec = dia if not length else f"{dia},{length}"
    id_tail = _code(dia) if not length else f"{_code(dia)}-{_code(length)}"
    return {
        "id": f"{prefix}-{id_tail}-{mat_code}",
        "零件類型": part,
        "尺寸": size,
        "SCH": "",
        "材質": mat,
        "類別": category,
        "單位": unit,
        "規格": f"{part},{spec},{mat}",
        "來源": "標準總庫",
        "備註": "",
    }


def _raw_item(prefix: str, part: str, category: str, size: str, spec: str, mat: str, mat_code: str, unit: str, *, icon: str = "") -> dict:
    row = {
        "id": f"{prefix}-{_code(size)}-{mat_code}",
        "零件類型": part,
        "尺寸": size,
        "SCH": "",
        "材質": mat,
        "類別": category,
        "單位": unit,
        "規格": spec,
        "來源": "標準總庫",
        "備註": "",
    }
    if icon:
        row["icon"] = icon
    return row


def build_catalog(taxonomy: dict[str, Any]) -> list[dict]:
    dns = _axis(taxonomy, "nominal_diameter")
    bolt_dias = _axis(taxonomy, "bolt_diameter")
    bolt_lengths = _axis(taxonomy, "bolt_length")
    items: list[dict] = []

    single_schedule_parts = [
        ("PIPE", "鋼管", "管材", "米"),
        ("EL90", "90°彎頭", "彎頭", "個"),
        ("EL45", "45°彎頭", "彎頭", "個"),
        ("TEE", "等徑三通", "三通", "個"),
        ("CROSS", "四通", "四通", "個"),
        ("CPLG", "接頭", "接頭", "個"),
        ("UNION", "由令", "由令", "組"),
        ("NIP", "短節", "短節", "支"),
        ("CAP", "管帽", "管帽", "個"),
        ("PLUG", "管塞", "管塞", "個"),
    ]
    for prefix, part, category, unit in single_schedule_parts:
        for size in dns:
            for sch in SCHEDULES:
                for mat, mat_code in MATERIALS:
                    items.append(_item(prefix, part, category, size, sch, mat, mat_code, unit))

    reducing_parts = [
        ("RTEE", "異徑三通", "三通", "主管尺寸", "分支尺寸"),
        ("RC", "同心大小頭", "大小頭", "大端尺寸", "小端尺寸"),
        ("RE", "偏心大小頭", "大小頭", "大端尺寸", "小端尺寸"),
        ("BUSH", "補心", "補心", "外牙尺寸", "內牙尺寸"),
    ]
    for prefix, part, category, primary_label, secondary_label in reducing_parts:
        for primary, secondary in _dual_size_pairs(dns):
            for sch in SCHEDULES:
                for mat, mat_code in MATERIALS:
                    items.append(
                        _dual_item(
                            prefix,
                            part,
                            category,
                            primary,
                            secondary,
                            sch,
                            mat,
                            mat_code,
                            "個",
                            primary_label,
                            secondary_label,
                        )
                    )

    olet_parts = [
        ("WOL", "Weldolet"),
        ("SOL", "Sockolet"),
        ("TOL", "ThreadOlet"),
    ]
    for prefix, part in olet_parts:
        for header, branch in _olet_pairs(dns):
            for sch in SCHEDULES:
                for mat, mat_code in MATERIALS:
                    items.append(
                        _dual_item(prefix, part, "Olet", header, branch, sch, mat, mat_code, "個", "主管尺寸", "分支尺寸")
                    )

    flange_parts = [
        ("FLG", "法蘭", "法蘭", "片"),
        ("BLF", "盲法蘭", "法蘭", "片"),
    ]
    for prefix, part, category, unit in flange_parts:
        for size in dns:
            for rating in FLANGE_RATINGS:
                for mat, mat_code in MATERIALS:
                    items.append(_item(prefix, part, category, size, rating, mat, mat_code, unit))

    for size in dns:
        for rating in FLANGE_RATINGS:
            for mat, mat_code in GASKET_MATERIALS:
                items.append(_item("GSK", "墊片", "墊片", size, rating, mat, mat_code, "片"))

    valve_parts = [
        ("GV", "閘閥", "閘閥"),
        ("BV", "球閥", "球閥"),
        ("GLV", "球心閥", "球心閥"),
        ("CV", "止回閥", "止回閥"),
        ("BFV", "蝶閥", "蝶閥"),
        ("KGV", "刀閘閥", "刀閘閥"),
        ("STR", "過濾器", "過濾器"),
        ("SG", "視鏡", "視鏡"),
        ("ORF", "限流孔板", "限流孔板"),
        ("FA", "阻火器", "阻火器"),
    ]
    for prefix, part, category in valve_parts:
        for size in dns:
            for rating in VALVE_RATINGS:
                for mat, mat_code in MATERIALS:
                    items.append(_item(prefix, part, category, size, rating, mat, mat_code, "個"))

    special_parts = [
        ("NOZ", "噴嘴", "噴嘴", "個"),
        ("MIX", "混合器", "混合器", "個"),
        ("EXP", "伸縮接頭", "伸縮接頭", "組"),
        ("HOSE", "軟管", "軟管", "條"),
    ]
    for prefix, part, category, unit in special_parts:
        for size in dns:
            for mat, mat_code in MATERIALS:
                items.append(_item(prefix, part, category, size, "通用", mat, mat_code, unit))

    for dia in bolt_dias:
        for length in bolt_lengths:
            for mat, mat_code in BOLT_MATERIALS:
                items.append(_bolt_item("BOLT", "螺栓", "螺栓", dia, length, mat, mat_code, "組"))
                items.append(_bolt_item("STUD", "牙條", "螺栓", dia, length, mat, mat_code, "組"))
        for mat, mat_code in BOLT_MATERIALS:
            items.append(_bolt_item("NUT", "螺帽", "螺帽", dia, "", mat, mat_code, "個"))
            items.append(_bolt_item("WSH", "華司", "華司", dia, "", mat, mat_code, "片"))

    for size in dns:
        for dia in bolt_dias:
            for mat, mat_code in BOLT_MATERIALS:
                row = _bolt_item("UBOLT", "U型螺栓", "U型螺栓", dia, size, mat, mat_code, "組")
                row["尺寸"] = f"{size}/{dia}"
                row["規格"] = f"U型螺栓,{size},{dia},{mat}"
                row["id"] = f"UBOLT-{_code(size)}-{_code(dia)}-{mat_code}"
                items.append(row)

    for prefix, (part, category, icon, specs) in STEEL_SECTION_SPECS.items():
        for spec in specs:
            for mat, mat_code in SUPPORT_MATERIALS:
                row = _raw_item(prefix, part, category, spec, f"{part},{spec},標準長度6000mm,{mat}", mat, mat_code, "米", icon=icon)
                row["標準分類"] = "標準型鋼"
                row["標準長度"] = "6000mm"
                items.append(row)

    for stock_size in PLATE_STOCK_SIZES:
        for thickness in PLATE_THICKNESSES:
            for mat, mat_code in SUPPORT_MATERIALS:
                size = f"{stock_size}x{thickness}"
                row = _raw_item("PLATE", "鋼板", "鋼板", size, f"鋼板,{stock_size},{thickness},{mat}", mat, mat_code, "張", icon="SteelPlate")
                row["標準分類"] = "標準鋼板"
                row["標準板尺寸"] = stock_size
                row["厚度"] = thickness
                items.append(row)

    for prefix, part in PIPE_SHOE_PARTS:
        for size in dns:
            for mat, mat_code in SUPPORT_MATERIALS:
                items.append(_raw_item(prefix, part, "管鞋", size, f"{part},{size},{mat}", mat, mat_code, "組", icon="PipeShoe"))

    for prefix, part in PIPE_CLAMP_PARTS:
        for size in dns:
            for mat, mat_code in SUPPORT_MATERIALS:
                items.append(_raw_item(prefix, part, "管夾", size, f"{part},{size},{mat}", mat, mat_code, "組", icon="PipeClamp"))

    for prefix, part, category, icon, unit in PIPE_SUPPORT_PARTS:
        sizes = SLIDE_PLATE_SIZES if category == "滑板" else dns
        for size in sizes:
            for mat, mat_code in SUPPORT_MATERIALS:
                items.append(_raw_item(prefix, part, category, size, f"{part},{size},{mat}", mat, mat_code, unit, icon=icon))

    for size in BASE_PLATE_SIZES:
        for mat, mat_code in SUPPORT_MATERIALS:
            row = _raw_item("BASEPL", "底板", "底板", size, f"底板,{size},{mat}", mat, mat_code, "片", icon="BasePlate")
            row["厚度"] = size.rsplit("x", 1)[-1] if "x" in size and size.rsplit("x", 1)[-1].endswith("t") else ""
            items.append(row)

    seen: set[str] = set()
    clean: list[dict] = []
    for row in items:
        key = str(row["id"])
        if key in seen:
            raise ValueError(f"duplicate material id: {key}")
        seen.add(key)
        clean.append(row)
    return clean


def write_catalog(root: Path) -> dict[str, int]:
    taxonomy = load_taxonomy(str(root))
    items = build_catalog(taxonomy)
    doc = {
        "items": items,
        "history": [],
        "meta": {
            "version": "4.0",
            "kind": "標準總庫",
            "generated_from": "records/material_taxonomy.json",
            "count": len(items),
            "priced": False,
            "note": "標準總庫只記品項與規格，不記價格；價格交採購/會計。",
        },
    }
    targets = [
        root / "records" / "material_pricebook.json",
        root / "records" / "seed" / "material_pricebook_seed.json",
    ]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"count": len(items)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = write_catalog(args.root.resolve())
    print(f"generated {result['count']} material catalog rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
