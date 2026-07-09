# -*- coding: utf-8 -*-
"""Compact material catalog rules and lazy expansion helpers.

The material master should not have to persist every size / SCH / material
combination. This module keeps the compact text rules as the source and expands
rows only for UI pages, exports, or id lookup.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from material_taxonomy import load_taxonomy, normalize_material, normalize_schedule, normalize_size


RULE_SCHEMA = "material_catalog_rules.v1"

DEFAULT_RULES: dict[str, Any] = {
    "schema_version": RULE_SCHEMA,
    "version": "2026.07.rules",
    "materials": {
        "pipe": ["SUS304", "SUS304L", "SUS316", "SUS316L", "SUS321", "A106 GR.B", "CS", "GI"],
        "fitting": ["SUS304", "SUS304L", "SUS316", "SUS316L", "SUS321", "A234 GR.WPB", "CS", "GI"],
        "flange": ["SUS304", "SUS304L", "SUS316", "SUS316L", "SUS321", "A105", "CS", "GI"],
        "bolt": ["SUS304", "SUS316", "CS", "HDG"],
        "support": ["A36/SS400", "SUS304", "SUS316", "GI"],
        "gasket": ["PTFE", "石墨", "金屬纏繞", "橡膠"],
    },
    "rules": [
        {"mode": "single_schedule", "prefix": "PIPE", "part": "鋼管", "cat": "管材", "icon": "Pipe", "unit": "米", "materials": "pipe"},
        {"mode": "single_schedule", "prefix": "EL90", "part": "90°彎頭", "cat": "彎頭", "icon": "Elbow", "unit": "個", "materials": "fitting"},
        {"mode": "single_schedule", "prefix": "EL45", "part": "45°彎頭", "cat": "彎頭", "icon": "Elbow", "unit": "個", "materials": "fitting"},
        {"mode": "single_schedule", "prefix": "TEE", "part": "等徑三通", "cat": "三通", "icon": "Tee", "unit": "個", "materials": "fitting"},
        {"mode": "single_schedule", "prefix": "CROSS", "part": "四通", "cat": "四通", "icon": "Cross", "unit": "個", "materials": "fitting"},
        {"mode": "single_schedule", "prefix": "CPLG", "part": "接頭", "cat": "接頭", "icon": "Coupling", "unit": "個", "materials": "fitting"},
        {"mode": "single_schedule", "prefix": "UNION", "part": "由令", "cat": "由令", "icon": "Union", "unit": "組", "materials": "fitting"},
        {"mode": "single_schedule", "prefix": "NIP", "part": "短節", "cat": "短節", "icon": "Nipple", "unit": "支", "materials": "fitting"},
        {"mode": "single_schedule", "prefix": "CAP", "part": "管帽", "cat": "管帽", "icon": "Cap", "unit": "個", "materials": "fitting"},
        {"mode": "single_schedule", "prefix": "PLUG", "part": "管塞", "cat": "管塞", "icon": "plug", "unit": "個", "materials": "fitting"},
        {"mode": "dual_schedule", "prefix": "RTEE", "part": "異徑三通", "cat": "三通", "icon": "Tee", "unit": "個", "materials": "fitting"},
        {"mode": "dual_schedule", "prefix": "RC", "part": "同心大小頭", "cat": "大小頭", "icon": "Reducer", "unit": "個", "materials": "fitting"},
        {"mode": "dual_schedule", "prefix": "RE", "part": "偏心大小頭", "cat": "大小頭", "icon": "Reducer", "unit": "個", "materials": "fitting"},
        {"mode": "dual_schedule", "prefix": "BUSH", "part": "補心", "cat": "補心", "icon": "Bushing", "unit": "個", "materials": "fitting"},
        {"mode": "olet", "prefix": "WOL", "part": "Weldolet", "cat": "Olet", "icon": "Olet", "unit": "個", "materials": "fitting"},
        {"mode": "olet", "prefix": "SOL", "part": "Sockolet", "cat": "Olet", "icon": "Olet", "unit": "個", "materials": "fitting"},
        {"mode": "olet", "prefix": "TOL", "part": "ThreadOlet", "cat": "Olet", "icon": "Olet", "unit": "個", "materials": "fitting"},
        {"mode": "rating", "prefix": "FLG", "part": "法蘭", "cat": "法蘭", "icon": "Flange", "unit": "片", "ratings": ["150#", "300#", "600#"], "materials": "flange"},
        {"mode": "rating", "prefix": "BLF", "part": "盲法蘭", "cat": "法蘭", "icon": "Flange", "unit": "片", "ratings": ["150#", "300#", "600#"], "materials": "flange"},
        {"mode": "rating", "prefix": "GSK", "part": "墊片", "cat": "墊片", "icon": "Gasket", "unit": "片", "ratings": ["150#", "300#", "600#"], "materials": "gasket"},
        {"mode": "rating", "prefix": "GV", "part": "閘閥", "cat": "閘閥", "icon": "GateValve", "unit": "個", "ratings": ["150#", "300#", "600#", "800#"], "materials": "flange"},
        {"mode": "rating", "prefix": "BV", "part": "球閥", "cat": "球閥", "icon": "BallValve", "unit": "個", "ratings": ["150#", "300#", "600#", "800#"], "materials": "flange"},
        {"mode": "rating", "prefix": "GLV", "part": "球心閥", "cat": "球心閥", "icon": "GlobeValve", "unit": "個", "ratings": ["150#", "300#", "600#", "800#"], "materials": "flange"},
        {"mode": "rating", "prefix": "CV", "part": "止回閥", "cat": "止回閥", "icon": "CheckValve", "unit": "個", "ratings": ["150#", "300#", "600#", "800#"], "materials": "flange"},
        {"mode": "bolt", "prefix": "BOLT", "part": "螺栓", "cat": "螺栓", "icon": "BoltNut", "unit": "組", "materials": "bolt"},
        {"mode": "bolt", "prefix": "STUD", "part": "牙條", "cat": "螺栓", "icon": "BoltNut", "unit": "組", "materials": "bolt"},
        {"mode": "fastener", "prefix": "NUT", "part": "螺帽", "cat": "螺帽", "icon": "BoltNut", "unit": "個", "materials": "bolt"},
        {"mode": "fastener", "prefix": "WSH", "part": "華司", "cat": "華司", "icon": "BoltNut", "unit": "片", "materials": "bolt"},
        {"mode": "u_bolt", "prefix": "UBOLT", "part": "U型螺栓", "cat": "U型螺栓", "icon": "BoltNut", "unit": "組", "materials": "bolt"},
        {"mode": "support", "prefix": "ANG", "part": "角鋼", "cat": "角鋼", "icon": "SteelSection", "unit": "米", "sizes": ["L40x40x5", "L50x50x6", "L65x65x6", "L75x75x9", "L100x100x10"], "materials": "support"},
        {"mode": "support", "prefix": "CH", "part": "槽鋼", "cat": "槽鋼", "icon": "SteelSection", "unit": "米", "sizes": ["C100x50x5", "C150x75x9", "C200x90x8", "C300x100x8.5"], "materials": "support"},
        {"mode": "support", "prefix": "PLATE", "part": "鋼板", "cat": "鋼板", "icon": "SteelPlate", "unit": "張", "sizes": ["1219x2438x3t", "1219x2438x6t", "1219x2438x9t", "1219x2438x12t", "1524x3048x16t"], "materials": "support"},
        {"mode": "support", "prefix": "BASEPL", "part": "底板", "cat": "底板", "icon": "BasePlate", "unit": "片", "sizes": ["100x100x6t", "150x150x9t", "200x200x12t", "250x250x16t"], "materials": "support"},
        {"mode": "support_dn", "prefix": "PCLAMP", "part": "管夾", "cat": "管夾", "icon": "PipeClamp", "unit": "組", "materials": "support"},
        {"mode": "support_dn", "prefix": "PSHOE", "part": "管鞋", "cat": "管鞋", "icon": "PipeShoe", "unit": "組", "materials": "support"},
    ],
}


def rules_path(root: Path) -> Path:
    return root / "records" / "material_catalog_rules.json"


def ensure_rules_file(root: Path) -> Path:
    path = rules_path(root)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_RULES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_rules(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    path = ensure_rules_file(root_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and data.get("schema_version") == RULE_SCHEMA:
            return data
    except Exception:
        pass
    return DEFAULT_RULES


def _axis(taxonomy: dict[str, Any], key: str) -> list[str]:
    values = (((taxonomy.get("axes") or {}).get(key) or {}).get("values") or [])
    return [str(v) for v in values if isinstance(v, str)]


def _code(value: Any) -> str:
    text = normalize_material(value) if "SUS" in str(value).upper() or str(value).strip().isdigit() else str(value or "")
    text = (
        text.upper()
        .replace("SCH", "S")
        .replace("#", "")
        .replace("SUS", "")
        .replace("A36/SS400", "AS")
        .replace("A106 GR.B", "A106B")
        .replace("A53 GR.B", "A53B")
        .replace("A234 GR.WPB", "A234WPB")
        .replace("A105", "A105")
        .replace("HDG", "HDG")
        .replace("GI", "GI")
        .replace("金屬纏繞", "SWG")
        .replace("石墨", "GRAPH")
        .replace("橡膠", "RUB")
        .replace("*", "X")
        .replace("/", "")
        .replace(".", "P")
        .replace(" ", "")
    )
    text = re.sub(r"[^A-Z0-9]+", "", text)
    return text or "GEN"


def _dn_number(size: str) -> int:
    try:
        return int(str(size).upper().replace("DN", ""))
    except ValueError:
        return 0


def _dual_pairs(dns: list[str], max_step: int = 4) -> Iterable[tuple[str, str]]:
    ordered = sorted(dns, key=_dn_number)
    for i, larger in enumerate(ordered):
        for smaller in ordered[max(0, i - max_step):i]:
            yield larger, smaller


def _olet_pairs(dns: list[str]) -> Iterable[tuple[str, str]]:
    ordered = sorted(dns, key=_dn_number)
    common = {15, 20, 25, 40, 50, 80, 100, 150}
    for header in ordered:
        h = _dn_number(header)
        for branch in ordered:
            b = _dn_number(branch)
            if b < h and (b in common or b >= h // 2):
                yield header, branch


def _materials(rule: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    value = rule.get("materials")
    if isinstance(value, str):
        return [normalize_material(x) for x in ((rules.get("materials") or {}).get(value) or [])]
    return [normalize_material(x) for x in (value or [])]


def _row(
    rule: dict[str, Any],
    size: str,
    sch: str,
    mat: str,
    *,
    spec_size: str = "",
    size1: str = "",
    size2: str = "",
    dimension_mode: str = "single",
) -> dict[str, Any]:
    sch = normalize_schedule(sch)
    mat = normalize_material(mat)
    size = normalize_size(size)
    spec_size = spec_size or size
    spec_code = _code(sch) if sch else "GEN"
    mid = f"{rule['prefix']}-{_code(size)}-{spec_code}-{_code(mat)}"
    return {
        "id": mid,
        "零件類型": rule["part"],
        "尺寸": size,
        "SCH": sch,
        "材質": mat,
        "類別": rule["cat"],
        "單位": rule["unit"],
        "規格": f"{rule['part']},{spec_size},{sch},{mat}".strip(","),
        "來源": "標準規則庫",
        "備註": "",
        "icon": rule.get("icon") or "",
        "尺寸1": normalize_size(size1) if size1 else "",
        "尺寸2": normalize_size(size2) if size2 else "",
        "dimension_mode": dimension_mode,
    }


def iter_catalog_rows(root: str | Path) -> Iterable[dict[str, Any]]:
    root_path = Path(root)
    taxonomy = load_taxonomy(str(root_path))
    rules = load_rules(root_path)
    dns = _axis(taxonomy, "nominal_diameter")
    schedules = ["SCH10", "SCH40", "SCH80", "XS", "XXS"]
    bolt_dias = _axis(taxonomy, "bolt_diameter")
    bolt_lengths = _axis(taxonomy, "bolt_length")
    for rule in rules.get("rules") or []:
        mats = _materials(rule, rules)
        mode = rule.get("mode")
        if mode == "single_schedule":
            for size in dns:
                for sch in schedules:
                    for mat in mats:
                        yield _row(rule, size, sch, mat, size1=size)
        elif mode == "dual_schedule":
            for a, b in _dual_pairs(dns):
                size = f"{a}x{b}"
                for sch in schedules:
                    for mat in mats:
                        yield _row(rule, size, sch, mat, spec_size=f"主尺寸:{a},分支尺寸:{b}", size1=a, size2=b, dimension_mode="dual")
        elif mode == "olet":
            for a, b in _olet_pairs(dns):
                size = f"{a}x{b}"
                for sch in schedules:
                    for mat in mats:
                        yield _row(rule, size, sch, mat, spec_size=f"主管尺寸:{a},分支尺寸:{b}", size1=a, size2=b, dimension_mode="dual")
        elif mode == "rating":
            for size in dns:
                for rating in rule.get("ratings") or []:
                    for mat in mats:
                        yield _row(rule, size, rating, mat, size1=size)
        elif mode == "bolt":
            for dia in bolt_dias:
                for length in bolt_lengths:
                    size = f"{dia}x{str(length).replace('L', '')}"
                    for mat in mats:
                        yield _row(rule, size, "", mat, spec_size=f"{dia},{length}", size1=dia, size2=length, dimension_mode="bolt")
        elif mode == "fastener":
            for dia in bolt_dias:
                for mat in mats:
                    yield _row(rule, dia, "", mat, size1=dia, dimension_mode="fastener")
        elif mode == "u_bolt":
            for size in dns:
                for dia in bolt_dias:
                    for mat in mats:
                        yield _row(rule, f"{size}/{dia}", "", mat, spec_size=f"{size},{dia}", size1=size, size2=dia, dimension_mode="pipe-fastener")
        elif mode == "support":
            for size in rule.get("sizes") or []:
                for mat in mats:
                    yield _row(rule, size, "", mat, size1=size)
        elif mode == "support_dn":
            for size in dns:
                for mat in mats:
                    yield _row(rule, size, "", mat, size1=size)


def _frontend_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id") or "",
        "part": row.get("零件類型") or "",
        "size": row.get("尺寸") or "",
        "sch": row.get("SCH") or "",
        "mat": row.get("材質") or "",
        "cat": row.get("類別") or "",
        "unit": row.get("單位") or "",
        "src": row.get("來源") or "",
        "remark": row.get("備註") or "",
        "type": row.get("Type") or "",
        "level": row.get("支撐級別") or "",
        "spec": row.get("規格") or "",
        "icon": row.get("icon") or "",
        "material_family": row.get("material_family") or "",
        "match_key": row.get("match_key") or "",
        "project_only": bool(row.get("project_only")),
        "source_designation": row.get("source_designation") or "",
        "size1": row.get("尺寸1") or "",
        "size2": row.get("尺寸2") or "",
        "dimension_mode": row.get("dimension_mode") or "",
    }


def row_matches(row: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    f = filters or {}
    mapping = {
        "icon": "icon",
        "part": "零件類型",
        "size": "尺寸",
        "size1": "尺寸1",
        "size2": "尺寸2",
        "sch": "SCH",
        "mat": "材質",
        "cat": "類別",
    }
    for key, row_key in mapping.items():
        value = str(f.get(key) or "").strip()
        if value and str(row.get(row_key) or "") != value:
            return False
    q = str(f.get("q") or "").strip().lower()
    if q:
        blob = " ".join(str(row.get(k) or "") for k in ["id", "零件類型", "尺寸", "SCH", "材質", "類別", "規格", "來源"]).lower()
        if q not in blob:
            return False
    return True


def query_catalog(root: str | Path, filters: dict[str, Any] | None = None, *, offset: int = 0, limit: int = 200) -> dict[str, Any]:
    total = 0
    items: list[dict[str, Any]] = []
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 200), 1000))
    for row in iter_catalog_rows(root):
        if not row_matches(row, filters):
            continue
        if total >= offset and len(items) < limit:
            items.append(_frontend_row(row))
        total += 1
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def rows_by_ids(root: str | Path, ids: Iterable[Any]) -> list[dict[str, Any]]:
    wanted = {str(x) for x in ids if str(x or "").strip()}
    found: dict[str, dict[str, Any]] = {}
    if not wanted:
        return []
    for row in iter_catalog_rows(root):
        rid = str(row.get("id") or "")
        if rid in wanted:
            found[rid] = _frontend_row(row)
            if len(found) == len(wanted):
                break
    return [found[x] for x in sorted(found)]


def _find_rule(rules: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    part = str(spec.get("part") or spec.get("零件類型") or "").strip()
    icon = str(spec.get("icon") or "").strip()
    cat = str(spec.get("cat") or spec.get("類別") or "").strip()
    candidates = []
    for rule in rules.get("rules") or []:
        if part and str(rule.get("part") or "") == part:
            candidates.append(rule)
    if not candidates and icon:
        candidates = [rule for rule in (rules.get("rules") or []) if str(rule.get("icon") or "") == icon]
    if cat:
        scoped = [rule for rule in candidates if str(rule.get("cat") or "") == cat]
        if scoped:
            candidates = scoped
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(f"零件類型不在材料規範中：{part or icon or cat}")
    names = "、".join(str(rule.get("part") or "") for rule in candidates[:6])
    raise ValueError(f"請先選明確零件類型：{names}")


def _required_dn(value: Any, allowed: set[str], label: str) -> str:
    size = normalize_size(value)
    if not size:
        raise ValueError(f"{label}不可空白")
    if size not in allowed:
        raise ValueError(f"{label}不在常用 DN 規範中：{size}")
    return size


def _validate_material(rule: dict[str, Any], rules: dict[str, Any], value: Any) -> str:
    mat = normalize_material(value)
    if not mat:
        raise ValueError("材質不可空白")
    allowed = set(_materials(rule, rules))
    if allowed and mat not in allowed:
        raise ValueError(f"材質不在「{rule.get('part')}」規範中：{mat}；請先把材質加入材料規則庫")
    return mat


def build_catalog_row(root: str | Path, spec: dict[str, Any]) -> dict[str, Any]:
    """Build one material row from controlled template axes.

    This is the self-built path: users choose a template and dimensions, then
    validation decides whether the resulting material is a valid project item.
    """
    root_path = Path(root)
    taxonomy = load_taxonomy(str(root_path))
    rules = load_rules(root_path)
    rule = _find_rule(rules, spec)
    mode = str(rule.get("mode") or "")
    dns = set(_axis(taxonomy, "nominal_diameter"))
    schedules = {"SCH10", "SCH40", "SCH80", "XS", "XXS"}
    bolt_dias = set(_axis(taxonomy, "bolt_diameter"))
    bolt_lengths = set(_axis(taxonomy, "bolt_length"))
    mat = _validate_material(rule, rules, spec.get("mat") or spec.get("材質"))
    sch = normalize_schedule(spec.get("sch") or spec.get("SCH") or "")

    if mode == "single_schedule":
        size = _required_dn(spec.get("size") or spec.get("size1") or spec.get("尺寸"), dns, "尺寸")
        if spec.get("size2"):
            raise ValueError(f"{rule.get('part')} 是單尺寸品項，不可填尺寸2")
        if sch not in schedules:
            raise ValueError(f"厚度/SCH 不在規範中：{sch or '空白'}")
        return _row(rule, size, sch, mat, size1=size)

    if mode in {"dual_schedule", "olet"}:
        size1 = _required_dn(spec.get("size1") or spec.get("primary_size") or spec.get("尺寸1"), dns, "尺寸1")
        size2 = _required_dn(spec.get("size2") or spec.get("secondary_size") or spec.get("尺寸2"), dns, "尺寸2")
        if size1 == size2:
            raise ValueError(f"{rule.get('part')} 必須是雙尺寸，尺寸1不可等於尺寸2")
        if _dn_number(size1) <= _dn_number(size2):
            raise ValueError(f"{rule.get('part')} 的尺寸1必須大於尺寸2")
        if sch not in schedules:
            raise ValueError(f"厚度/SCH 不在規範中：{sch or '空白'}")
        label1, label2 = ("主管尺寸", "分支尺寸") if mode == "olet" else ("主尺寸", "分支尺寸")
        return _row(
            rule,
            f"{size1}x{size2}",
            sch,
            mat,
            spec_size=f"{label1}:{size1},{label2}:{size2}",
            size1=size1,
            size2=size2,
            dimension_mode="dual",
        )

    if mode == "rating":
        size = _required_dn(spec.get("size") or spec.get("size1") or spec.get("尺寸"), dns, "尺寸")
        ratings = {str(x) for x in (rule.get("ratings") or [])}
        if sch not in ratings:
            raise ValueError(f"壓力等級不在規範中：{sch or '空白'}")
        return _row(rule, size, sch, mat, size1=size)

    if mode == "bolt":
        dia = str(spec.get("size1") or spec.get("diameter") or "").strip().upper()
        length = str(spec.get("size2") or spec.get("length") or "").strip().upper()
        if dia not in bolt_dias:
            raise ValueError(f"螺栓直徑不在規範中：{dia or '空白'}")
        if length and not length.startswith("L"):
            length = "L" + length
        if length not in bolt_lengths:
            raise ValueError(f"螺栓長度不在規範中：{length or '空白'}")
        return _row(rule, f"{dia}x{length.replace('L', '')}", "", mat, spec_size=f"{dia},{length}", size1=dia, size2=length, dimension_mode="bolt")

    if mode == "fastener":
        dia = str(spec.get("size") or spec.get("size1") or "").strip().upper()
        if dia not in bolt_dias:
            raise ValueError(f"緊固件尺寸不在規範中：{dia or '空白'}")
        return _row(rule, dia, "", mat, size1=dia, dimension_mode="fastener")

    if mode == "u_bolt":
        pipe_size = _required_dn(spec.get("size1") or spec.get("pipe_size"), dns, "管徑")
        dia = str(spec.get("size2") or spec.get("diameter") or "").strip().upper()
        if dia not in bolt_dias:
            raise ValueError(f"螺栓直徑不在規範中：{dia or '空白'}")
        return _row(rule, f"{pipe_size}/{dia}", "", mat, spec_size=f"{pipe_size},{dia}", size1=pipe_size, size2=dia, dimension_mode="pipe-fastener")

    if mode in {"support", "support_dn"}:
        allowed_sizes = set(rule.get("sizes") or []) if mode == "support" else dns
        size = str(spec.get("size") or spec.get("size1") or "").strip()
        size = normalize_size(size) if mode == "support_dn" else size
        if size not in allowed_sizes:
            raise ValueError(f"尺寸不在「{rule.get('part')}」規範中：{size or '空白'}")
        return _row(rule, size, "", mat, size1=size, dimension_mode="single")

    raise ValueError(f"尚未支援此材料規格模式：{mode}")


def build_frontend_item(root: str | Path, spec: dict[str, Any]) -> dict[str, Any]:
    return _frontend_row(build_catalog_row(root, spec))


def catalog_summary(root: str | Path) -> dict[str, Any]:
    total = 0
    counts: dict[str, int] = {}
    values = {k: set() for k in ["part", "size", "size1", "size2", "sch", "mat", "cat", "dimension_mode"]}
    by_icon: dict[str, dict[str, Any]] = {}
    for row in iter_catalog_rows(root):
        total += 1
        icon = str(row.get("icon") or "Other")
        counts[icon] = counts.get(icon, 0) + 1
        target = by_icon.setdefault(
            icon,
            {
                "count": 0,
                "part": set(),
                "size": set(),
                "size1": set(),
                "size2": set(),
                "sch": set(),
                "mat": set(),
                "cat": set(),
                "dimension_mode": set(),
                "by_part": {},
            },
        )
        target["count"] += 1
        pairs = {
            "part": row.get("零件類型"),
            "size": row.get("尺寸"),
            "size1": row.get("尺寸1"),
            "size2": row.get("尺寸2"),
            "sch": row.get("SCH"),
            "mat": row.get("材質"),
            "cat": row.get("類別"),
            "dimension_mode": row.get("dimension_mode"),
        }
        part_key = str(row.get("零件類型") or "")
        part_target = None
        if part_key:
            part_target = target["by_part"].setdefault(
                part_key,
                {
                    "count": 0,
                    "size": set(),
                    "size1": set(),
                    "size2": set(),
                    "sch": set(),
                    "mat": set(),
                    "cat": set(),
                    "dimension_mode": set(),
                },
            )
            part_target["count"] += 1
        for key, value in pairs.items():
            if value:
                values[key].add(str(value))
                target[key].add(str(value))
                if part_target is not None and key != "part":
                    part_target[key].add(str(value))
    by_icon_out = {}
    for icon, data in by_icon.items():
        item = {k: (sorted(v) if isinstance(v, set) else v) for k, v in data.items() if k != "by_part"}
        item["by_part"] = {
            part: {k: (sorted(v) if isinstance(v, set) else v) for k, v in pdata.items()}
            for part, pdata in (data.get("by_part") or {}).items()
        }
        by_icon_out[icon] = item
    return {
        "schema_version": RULE_SCHEMA,
        "total": total,
        "counts": counts,
        "values": {k: sorted(v) for k, v in values.items()},
        "by_icon": by_icon_out,
    }


def all_catalog_rows(root: str | Path) -> list[dict[str, Any]]:
    return [row for row in iter_catalog_rows(root)]
