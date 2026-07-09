# -*- coding: utf-8 -*-
"""Read-only lookup wrapper around the existing weld control table manager."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from change_order import Spec
from utils import resolve_col
from weld_control import init_weld_manager_from_settings


REAL_JOINT_ATTRIBUTES = frozenset({"焊口", "管牙製作安裝"})
REAL_JOINT_PROPERTIES = frozenset({"原圖焊口", "修改", "新增"})


def normalize_series_raw(series: Any) -> str:
    """Normalize user-facing serial input to the raw key stored by weld_control."""
    text = "" if series is None else str(series).strip()
    return text.lstrip("0") or "0"


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_value(row: dict[str, Any], column_name: str) -> Any:
    resolved = resolve_col(column_name, row.keys())
    return row.get(resolved)


def _first_row_text(row: dict[str, Any], column_names: Iterable[str], *, exact_for_short_names: bool = True) -> Optional[str]:
    for column_name in column_names:
        short_name = len(column_name.replace(".", "").replace(" ", "")) <= 3
        if exact_for_short_names and short_name:
            text = _text(_exact_normalized_row_value(row, column_name))
            if text is not None:
                return text
            continue
        value = _row_value(row, column_name)
        text = _text(value)
        if text is not None:
            return text
    return None


def _config_column_names(config: dict[str, Any], key: str, fallback_names: Iterable[str]) -> list[str]:
    names: list[str] = []
    configured = _text(config.get(key))
    if configured is not None:
        names.append(configured)
    for name in fallback_names:
        text = _text(name)
        if text is not None and text not in names:
            names.append(text)
    return names


def _configured_row_text(
    row: dict[str, Any],
    config: dict[str, Any],
    key: str,
    fallback_names: Iterable[str],
    *,
    exact_for_short_names: bool = True,
) -> Optional[str]:
    return _first_row_text(
        row,
        _config_column_names(config, key, fallback_names),
        exact_for_short_names=exact_for_short_names,
    )


def _exact_normalized_row_value(row: dict[str, Any], column_name: str) -> Any:
    target = column_name.replace(" ", "").replace("\n", "").lower()
    for key in row.keys():
        if str(key).replace(" ", "").replace("\n", "").lower() == target:
            return row.get(key)
    return None


def _configured_exact_row_text(
    row: dict[str, Any],
    config: dict[str, Any],
    key: str,
    fallback_names: Iterable[str],
) -> Optional[str]:
    for column_name in _config_column_names(config, key, fallback_names):
        text = _text(_exact_normalized_row_value(row, column_name))
        if text is not None:
            return text
    return None


def _is_real_joint(row: dict[str, Any], config: dict[str, Any] | None = None) -> bool:
    config = config if isinstance(config, dict) else {}
    attr = _configured_exact_row_text(row, config, "col_attribute_1", ("屬性.1", "屬性1"))
    if attr is not None:
        return attr in REAL_JOINT_ATTRIBUTES

    # Some補登/結算管制表 variants do not carry 屬性.1.  In those files the
    # weld detail sheet marks actual rows through 焊口屬性, or simply consists of
    # weld-number rows with spec columns.  Keep the old strict path when 屬性.1
    # exists, but accept these detail-only variants.
    prop = _configured_row_text(
        row,
        config,
        "col_attribute_2",
        ("焊口屬性", "屬性.2", "屬性2", "屬性", "分類"),
        exact_for_short_names=False,
    )
    if prop is not None:
        return prop in REAL_JOINT_PROPERTIES or "焊口" in prop

    return bool(
        _configured_row_text(row, config, "col_weld_no", ("焊口編號", "銲口編號", "焊口碼"))
        and any(
            _configured_row_text(row, config, key, names)
            for key, names in (
                ("col_size", ("尺寸", "SIZE", "口徑", "管徑")),
                ("col_thickness", ("厚度", "SCH", "Schedule", "管厚")),
                ("col_material", ("材質", "MATERIAL", "鋼種")),
                ("col_weld_type", ("銲接型式", "焊接型式", "焊口型式")),
            )
        )
    )


class WeldLookup:
    """Read-only weld-control-table lookup for the new change-order model."""

    def __init__(self, manager=None, *, serial_format: str = "raw"):
        self.manager = manager if manager is not None else init_weld_manager_from_settings()
        self.serial_format = serial_format or "raw"

    @property
    def _config(self) -> dict[str, Any]:
        config = getattr(self.manager, "config", {}) if self.manager is not None else {}
        return config if isinstance(config, dict) else {}

    def lookup_spec(self, series: Any, base: Any) -> Spec | None:
        """Return the existing weld spec for ``(series, base)`` from real joint rows."""
        info = self.lookup_info(series, base)
        if info is not None:
            return Spec(
                size=info.get("size"),
                sch=info.get("sch"),
                material=info.get("material"),
                weld_type=info.get("weld_type"),
            )
        return None

    def lookup_info(self, series: Any, base: Any) -> dict[str, Optional[str]] | None:
        """Return weld spec plus report-facing metadata from the control table."""
        weld_id = "" if base is None else str(base).strip()
        if not weld_id:
            return None

        for row in self._real_rows_by_series(series):
            config = self._config
            if _configured_row_text(row, config, "col_weld_no", ("焊口編號", "銲口編號", "焊口碼")) == weld_id:
                budget_no = _configured_row_text(row, config, "col_budget_no", ("預算編號", "Budget No", "BudgetNo", "Budget"))
                db_value = _configured_row_text(
                    row,
                    config,
                    "col_db",
                    ("DB數", "DB", "D.B.", "DI", "D.I.", "Dia-Inch", "DIA INCH", "管徑吋數"),
                )
                inside_diameter = _configured_row_text(row, config, "col_inside_diameter", ("I.D", "I.D.", "ID", "內徑"))
                return {
                    "size": _configured_row_text(row, config, "col_size", ("尺寸", "SIZE", "口徑", "管徑")),
                    "sch": _configured_row_text(row, config, "col_thickness", ("厚度", "SCH", "Schedule", "管厚")),
                    "material": _configured_row_text(row, config, "col_material", ("材質", "MATERIAL", "鋼種")),
                    "weld_type": _configured_row_text(row, config, "col_weld_type", ("銲接型式", "焊接型式", "焊口型式")),
                    "db": db_value,
                    "budget_no": budget_no,
                    "inside_diameter": inside_diameter,
                }
        return None

    def existing_weld_ids(self, series: Any) -> list[str]:
        """List existing real joint IDs for a serial, preserving table order."""
        ids: list[str] = []
        for row in self._real_rows_by_series(series):
            weld_id = _configured_row_text(row, self._config, "col_weld_no", ("焊口編號", "銲口編號", "焊口碼"))
            if weld_id is not None:
                ids.append(weld_id)
        return ids

    def exists(self, series: Any, weld_id: Any) -> bool:
        """Check whether a weld-control-table primary key already exists."""
        if not self._manager_available():
            return False
        return bool(self.manager.check_exists(
            normalize_series_raw(series),
            "" if weld_id is None else str(weld_id).strip(),
        ))

    def _real_rows_by_series(self, series: Any) -> Iterable[dict[str, Any]]:
        if not self._manager_available():
            return []
        rows = self.manager.get_all_welds_by_serial(normalize_series_raw(series))
        return [row for row in rows if _is_real_joint(row, self._config)]

    def _manager_available(self) -> bool:
        if self.manager is None:
            return False
        is_configured = getattr(self.manager, "is_configured", None)
        return not callable(is_configured) or bool(is_configured())


__all__ = ["REAL_JOINT_ATTRIBUTES", "WeldLookup", "normalize_series_raw"]
