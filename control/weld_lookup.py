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


def _exact_normalized_row_value(row: dict[str, Any], column_name: str) -> Any:
    target = column_name.replace(" ", "").replace("\n", "").lower()
    for key in row.keys():
        if str(key).replace(" ", "").replace("\n", "").lower() == target:
            return row.get(key)
    return None


def _is_real_joint(row: dict[str, Any]) -> bool:
    attr = _text(_exact_normalized_row_value(row, "屬性.1"))
    if attr is not None:
        return attr in REAL_JOINT_ATTRIBUTES

    # Some補登/結算管制表 variants do not carry 屬性.1.  In those files the
    # weld detail sheet marks actual rows through 焊口屬性, or simply consists of
    # weld-number rows with spec columns.  Keep the old strict path when 屬性.1
    # exists, but accept these detail-only variants.
    prop = _text(_row_value(row, "焊口屬性")) or _text(_row_value(row, "屬性"))
    if prop is not None:
        return prop in REAL_JOINT_PROPERTIES or "焊口" in prop

    return bool(
        _text(_row_value(row, "焊口編號"))
        and any(_text(_row_value(row, name)) for name in ("尺寸", "厚度", "材質", "銲接型式"))
    )


class WeldLookup:
    """Read-only weld-control-table lookup for the new change-order model."""

    def __init__(self, manager=None, *, serial_format: str = "raw"):
        self.manager = manager if manager is not None else init_weld_manager_from_settings()
        self.serial_format = serial_format or "raw"

    def lookup_spec(self, series: Any, base: Any) -> Spec | None:
        """Return the existing weld spec for ``(series, base)`` from real joint rows."""
        weld_id = "" if base is None else str(base).strip()
        if not weld_id:
            return None

        for row in self._real_rows_by_series(series):
            if _text(_row_value(row, "焊口編號")) == weld_id:
                return Spec(
                    size=_text(_row_value(row, "尺寸")),
                    sch=_text(_row_value(row, "厚度")),
                    material=_text(_row_value(row, "材質")),
                    weld_type=_text(_row_value(row, "銲接型式")),
                )
        return None

    def existing_weld_ids(self, series: Any) -> list[str]:
        """List existing real joint IDs for a serial, preserving table order."""
        ids: list[str] = []
        for row in self._real_rows_by_series(series):
            weld_id = _text(_row_value(row, "焊口編號"))
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
        return [row for row in rows if _is_real_joint(row)]

    def _manager_available(self) -> bool:
        if self.manager is None:
            return False
        is_configured = getattr(self.manager, "is_configured", None)
        return not callable(is_configured) or bool(is_configured())


__all__ = ["REAL_JOINT_ATTRIBUTES", "WeldLookup", "normalize_series_raw"]
