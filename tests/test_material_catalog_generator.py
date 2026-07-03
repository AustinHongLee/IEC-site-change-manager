# -*- coding: utf-8 -*-

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from generate_material_catalog import build_catalog  # noqa: E402


def _taxonomy():
    return {
        "axes": {
            "nominal_diameter": {"values": ["DN15", "DN20", "DN25", "DN40", "DN50", "DN80"]},
            "bolt_diameter": {"values": ["M12", "M16"]},
            "bolt_length": {"values": ["L50", "L80"]},
        }
    }


def test_reducers_and_olets_are_dual_size_items():
    rows = build_catalog(_taxonomy())
    by_id = {row["id"]: row for row in rows}

    reducer = by_id["RC-DN50XDN25-S40-CS"]
    assert reducer["零件類型"] == "同心大小頭"
    assert reducer["尺寸"] == "DN50xDN25"
    assert reducer["大端尺寸"] == "DN50"
    assert reducer["小端尺寸"] == "DN25"

    olet = by_id["WOL-DN80XDN40-S40-CS"]
    assert olet["零件類型"] == "Weldolet"
    assert olet["尺寸"] == "DN80xDN40"
    assert olet["主管尺寸"] == "DN80"
    assert olet["分支尺寸"] == "DN40"

    assert "RC-DN50-S40-CS" not in by_id
    assert "WOL-DN80-S40-CS" not in by_id


def test_bolts_do_not_use_pipe_dn_or_schedule_axes():
    rows = build_catalog(_taxonomy())
    by_id = {row["id"]: row for row in rows}

    bolt = by_id["BOLT-M16-L50-CS"]
    assert bolt["尺寸"] == "M16x50"
    assert bolt["SCH"] == ""
    assert "DN" not in bolt["id"]

    nut = by_id["NUT-M16-CS"]
    assert nut["尺寸"] == "M16"
    assert nut["SCH"] == ""

    ubolt = by_id["UBOLT-DN50-M16-CS"]
    assert ubolt["尺寸"] == "DN50/M16"
    assert ubolt["SCH"] == ""


def test_catalog_includes_structural_steel_plate_and_support_parts_without_type_assemblies():
    rows = build_catalog(_taxonomy())
    by_id = {row["id"]: row for row in rows}

    angle = by_id["ANG-L50X50X6-AS"]
    assert angle["零件類型"] == "角鋼"
    assert angle["類別"] == "角鋼"
    assert angle["標準分類"] == "標準型鋼"
    assert angle["標準長度"] == "6000mm"

    plate = by_id["PLATE-1219X2438X12T-AS"]
    assert plate["零件類型"] == "鋼板"
    assert plate["標準分類"] == "標準鋼板"
    assert plate["標準板尺寸"] == "1219x2438"
    assert plate["厚度"] == "12t"

    shoe = by_id["PSHOE-STD-DN50-AS"]
    assert shoe["零件類型"] == "標準管鞋"
    assert shoe["類別"] == "管鞋"

    clamp = by_id["PCLAMP-ELEC-DN50-GI"]
    assert clamp["零件類型"] == "電工管夾"
    assert clamp["類別"] == "管夾"

    base = by_id["BASEPL-150X150X9T-AS"]
    assert base["零件類型"] == "底板"
    assert base["尺寸"] == "150x150x9t"
    assert base["厚度"] == "9t"

    assert not any(row.get("支撐級別") == "組件" for row in rows)
    assert not any(str(row.get("零件類型", "")).startswith("Type") for row in rows)
    assert not any(row.get("Type") for row in rows)
    assert not any("依圖" in str(value) for row in rows for value in row.values())
