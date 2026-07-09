# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "tools"))

from generate_material_catalog import write_rules  # noqa: E402
from material_catalog_rules import all_catalog_rows  # noqa: E402


def _write_taxonomy(root: Path) -> None:
    records = root / "records"
    records.mkdir(parents=True, exist_ok=True)
    (records / "material_taxonomy.json").write_text(
        json.dumps(
            {
                "schema_version": "material_taxonomy.v1",
                "axes": {
                    "nominal_diameter": {"values": ["DN15", "DN20", "DN25", "DN40", "DN50", "DN80"]},
                    "bolt_diameter": {"values": ["M12", "M16"]},
                    "bolt_length": {"values": ["L50", "L80"]},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _rows(tmp_path: Path) -> list[dict]:
    _write_taxonomy(tmp_path)
    write_rules(tmp_path / "records" / "material_catalog_rules.json")
    return all_catalog_rows(tmp_path)


def test_write_rules_outputs_compact_rule_schema(tmp_path):
    path = tmp_path / "records" / "material_catalog_rules.json"

    write_rules(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "material_catalog_rules.v1"
    assert data["rules"]
    assert any(rule["mode"] == "dual_schedule" and rule["part"] == "同心大小頭" for rule in data["rules"])
    assert any(rule["mode"] == "bolt" and rule["part"] == "螺栓" for rule in data["rules"])


def test_reducers_and_olets_are_dual_size_items(tmp_path):
    by_id = {row["id"]: row for row in _rows(tmp_path)}

    reducer = by_id["RC-DN50XDN25-S40-CS"]
    assert reducer["零件類型"] == "同心大小頭"
    assert reducer["尺寸"] == "DN50xDN25"
    assert reducer["尺寸1"] == "DN50"
    assert reducer["尺寸2"] == "DN25"
    assert reducer["dimension_mode"] == "dual"

    olet = by_id["WOL-DN80XDN40-S40-CS"]
    assert olet["零件類型"] == "Weldolet"
    assert olet["尺寸"] == "DN80xDN40"
    assert olet["尺寸1"] == "DN80"
    assert olet["尺寸2"] == "DN40"
    assert olet["dimension_mode"] == "dual"

    assert "RC-DN50-S40-CS" not in by_id
    assert "WOL-DN80-S40-CS" not in by_id


def test_bolts_do_not_use_pipe_dn_or_schedule_axes(tmp_path):
    by_id = {row["id"]: row for row in _rows(tmp_path)}

    bolt = by_id["BOLT-M16X50-GEN-CS"]
    assert bolt["尺寸"] == "M16x50"
    assert bolt["SCH"] == ""
    assert bolt["dimension_mode"] == "bolt"

    nut = by_id["NUT-M16-GEN-CS"]
    assert nut["尺寸"] == "M16"
    assert nut["SCH"] == ""

    ubolt = by_id["UBOLT-DN50M16-GEN-CS"]
    assert ubolt["尺寸"] == "DN50/M16"
    assert ubolt["SCH"] == ""
    assert ubolt["dimension_mode"] == "pipe-fastener"


def test_catalog_includes_structural_steel_plate_and_support_parts_without_type_assemblies(tmp_path):
    rows = _rows(tmp_path)
    by_id = {row["id"]: row for row in rows}

    angle = by_id["ANG-L50X50X6-GEN-AS"]
    assert angle["零件類型"] == "角鋼"
    assert angle["類別"] == "角鋼"

    plate = by_id["PLATE-1219X2438X12T-GEN-AS"]
    assert plate["零件類型"] == "鋼板"
    assert plate["尺寸"] == "1219x2438x12t"

    shoe = by_id["PSHOE-DN50-GEN-AS"]
    assert shoe["零件類型"] == "管鞋"
    assert shoe["類別"] == "管鞋"

    clamp = by_id["PCLAMP-DN50-GEN-GI"]
    assert clamp["零件類型"] == "管夾"
    assert clamp["類別"] == "管夾"

    base = by_id["BASEPL-150X150X9T-GEN-AS"]
    assert base["零件類型"] == "底板"
    assert base["尺寸"] == "150x150x9t"

    assert not any(row.get("支撐級別") == "組件" for row in rows)
    assert not any(str(row.get("零件類型", "")).startswith("Type") for row in rows)
    assert not any(row.get("Type") for row in rows)
    assert not any("依圖" in str(value) for row in rows for value in row.values())


def test_generate_material_catalog_cli_can_write_expanded_audit(tmp_path):
    rules = tmp_path / "rules.json"
    expanded = tmp_path / "expanded.json"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "generate_material_catalog.py"),
            "--output",
            str(rules),
            "--expanded",
            str(expanded),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert rules.exists()
    data = json.loads(expanded.read_text(encoding="utf-8"))
    assert data["meta"]["kind"] == "expanded-audit"
    assert data["items"]
