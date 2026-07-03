# -*- coding: utf-8 -*-
"""Bridge IEC support Type designations to material rows.

The pipe-support truth lives in the sibling ``for_iec_support`` project.  This
module keeps the dependency at the boundary: call its calculator, preserve the
raw BOM entries, then project those entries into the light material-row shape
used by this app.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from material_taxonomy import normalize_material, normalize_schedule, normalize_size


_RUNNER = r"""
import json
import sys
from pathlib import Path

app_dir = Path(sys.argv[1])
designation = sys.argv[2]
overrides = json.loads(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else {}
sys.path.insert(0, str(app_dir))

from core.calculator import analyze_single


def entry_dict(e):
    return {
        "item_no": getattr(e, "item_no", 0),
        "name": getattr(e, "name", ""),
        "spec": getattr(e, "spec", ""),
        "display_spec": getattr(e, "display_spec", getattr(e, "spec", "")),
        "length": getattr(e, "length", 0),
        "width": getattr(e, "width", 0),
        "material": getattr(e, "material", ""),
        "quantity": getattr(e, "quantity", 1),
        "unit": getattr(e, "unit", ""),
        "category": getattr(e, "category", ""),
        "remark": getattr(e, "display_remark", getattr(e, "remark", "")),
        "role": getattr(e, "role", ""),
        "weight": getattr(e, "weight_output", 0),
        "unit_weight": getattr(e, "unit_weight", 0),
        "length_subtotal": getattr(e, "length_subtotal", 0),
        "qty_subtotal": getattr(e, "qty_subtotal", 0),
        "part_key": getattr(e, "part_key", ""),
        "stock_id": getattr(e, "stock_id", ""),
        "item_class": getattr(e, "item_class", ""),
        "manufacturing_type": getattr(e, "manufacturing_type", ""),
    }


result = analyze_single(designation, overrides=overrides)
payload = {
    "designation": getattr(result, "fullstring", designation),
    "error": getattr(result, "error", ""),
    "warnings": list(getattr(result, "warnings", []) or []),
    "total_weight": getattr(result, "total_weight", 0),
    "meta": getattr(result, "meta", {}) or {},
    "entries": [entry_dict(e) for e in getattr(result, "entries", [])],
}
print(json.dumps(payload, ensure_ascii=False))
"""


def normalize_designation(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = text.replace("－", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", text)


def support_type_id(designation: str) -> str:
    raw = normalize_designation(designation).split("-", 1)[0]
    if raw[-1:].isalpha() and raw[:-1].isdigit():
        return f"{int(raw[:-1]):02d}{raw[-1]}"
    return f"{int(raw):02d}" if raw.isdigit() else raw


def find_support_app_dir(project_root: str | Path | None = None) -> Path | None:
    env = os.environ.get("CO_SUPPORT_APP_DIR") or os.environ.get("FOR_IEC_SUPPORT_APP_DIR")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    if project_root:
        root = Path(project_root).resolve()
        candidates.append(root.parent / "for_iec_support" / "python_app")
    here = Path(__file__).resolve()
    candidates.append(here.parents[2] / "for_iec_support" / "python_app")

    for candidate in candidates:
        if (candidate / "core" / "calculator.py").is_file():
            return candidate
    return None


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_num(value: Any) -> str:
    number = _num(value)
    if number == int(number):
        return str(int(number))
    return f"{number:g}"


def _unit(value: str, *, fallback: str = "個") -> str:
    up = str(value or "").strip().upper()
    return {
        "M": "米",
        "MTR": "米",
        "MM": "mm",
        "PC": "片",
        "PCS": "片",
        "EA": "個",
        "SET": "組",
    }.get(up, value or fallback)


def _pipe_size_sch(spec: str) -> tuple[str, str]:
    if "*" in spec:
        size, sch = spec.split("*", 1)
        return normalize_size(size), normalize_schedule(sch)
    return normalize_size(spec), ""


def _plate_size(entry: dict[str, Any]) -> str:
    length = _num(entry.get("length"))
    width = _num(entry.get("width"))
    thick = str(entry.get("display_spec") or entry.get("spec") or "").strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", thick):
        thick = _fmt_num(thick) + "t"
    if length and width and thick:
        return f"{_fmt_num(length)}x{_fmt_num(width)}x{thick}"
    return normalize_size(thick)


def _qty(entry: dict[str, Any], category: str) -> Any:
    if category == "管材":
        subtotal = _num(entry.get("length_subtotal"))
        if subtotal:
            return round(subtotal, 3)
        length_m = _num(entry.get("length")) * max(_num(entry.get("quantity")), 1) / 1000
        return round(length_m, 3) if length_m else 1
    q = _num(entry.get("quantity"))
    return int(q) if q == int(q) else q


def _category(entry: dict[str, Any]) -> str:
    name = str(entry.get("name") or "").upper()
    cat = str(entry.get("category") or "")
    role = str(entry.get("role") or "")
    if role == "pipe" or "管路" in cat or name in {"PIPE", "管路"}:
        return "管材"
    if "U-BOLT" in name or role == "u_bolt":
        return "U型螺栓"
    if "NUT" in name:
        return "螺帽"
    if "BOLT" in name or "螺栓" in cat:
        return "螺栓"
    if role == "base_plate" or "BASE PLATE" in name or "底板" in name:
        return "底板"
    if "PLATE" in name or "鋼板" in cat:
        return "鋼板"
    if "ANGLE" in name or "角鋼" in name:
        return "角鋼"
    if "CHANNEL" in name or "槽鋼" in name:
        return "槽鋼"
    if "H型鋼" in name or name.startswith("H-"):
        return "H型鋼"
    return cat.replace("類", "") or "其他"


def _part(entry: dict[str, Any], category: str) -> str:
    name = str(entry.get("name") or "").strip()
    if category == "管材" and name in {"管路", "PIPE"}:
        return "支撐管"
    if category == "底板":
        return name or "底板"
    return name or category


def entry_to_material(entry: dict[str, Any], designation: str, type_id: str) -> dict[str, Any]:
    category = _category(entry)
    spec = str(entry.get("display_spec") or entry.get("spec") or "").strip()
    if category == "管材":
        size, sch = _pipe_size_sch(spec)
    elif category in {"鋼板", "底板"}:
        size, sch = _plate_size(entry), ""
    elif category in {"螺栓", "螺帽", "U型螺栓"}:
        size, sch = spec, ""
    else:
        size, sch = normalize_size(spec), ""

    item_no = int(_num(entry.get("item_no")) or 0)
    unit = "米" if category == "管材" else _unit(str(entry.get("unit") or ""))
    if category == "螺帽":
        unit = "個"
    elif category in {"螺栓", "U型螺栓"}:
        unit = "組" if str(entry.get("unit") or "").strip().upper() == "SET" else unit
    return {
        "id": f"SUPPORT-{normalize_designation(designation)}-{item_no:02d}",
        "part": _part(entry, category),
        "size": size,
        "sch": sch,
        "mat": normalize_material(entry.get("material") or ""),
        "qty": _qty(entry, category),
        "unit": unit,
        "remark": str(entry.get("remark") or ""),
        "cat": category,
        "type": f"Type{type_id}",
        "spec": spec,
        "source_designation": normalize_designation(designation),
        "source_item_no": item_no,
        "weight": round(_num(entry.get("weight")), 3),
        "role": entry.get("role") or "",
        "manufacturing_type": entry.get("manufacturing_type") or "",
    }


def analyze_support_bom(
    designation: str,
    *,
    project_root: str | Path | None = None,
    support_app_dir: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    normalized = normalize_designation(designation)
    if not normalized:
        raise ValueError("請輸入管架編碼，例如 01-2B-03C")

    app_dir = Path(support_app_dir) if support_app_dir else find_support_app_dir(project_root)
    if not app_dir or not (app_dir / "core" / "calculator.py").is_file():
        raise FileNotFoundError("找不到 for_iec_support/python_app，無法展開管架材料")

    proc = subprocess.run(
        [sys.executable, "-c", _RUNNER, str(app_dir), normalized, json.dumps(overrides or {}, ensure_ascii=False)],
        cwd=str(app_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail or f"for_iec_support calculator failed ({proc.returncode})")

    raw = json.loads(proc.stdout)
    type_id = support_type_id(normalized)
    entries = raw.get("entries") if isinstance(raw.get("entries"), list) else []
    materials = [entry_to_material(e, normalized, type_id) for e in entries if isinstance(e, dict)]
    return {
        "designation": normalized,
        "type": type_id,
        "status": "error" if raw.get("error") else ("review" if raw.get("warnings") else "ok"),
        "error": raw.get("error") or "",
        "warnings": raw.get("warnings") or [],
        "total_weight": round(_num(raw.get("total_weight")), 3),
        "entries": entries,
        "materials": materials,
        "support_app_dir": str(app_dir),
    }
