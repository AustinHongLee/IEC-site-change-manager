# -*- coding: utf-8 -*-
"""Headless workflow builder for canonical ChangeOrder records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from change_order import (
    AuditEntry,
    Authorization,
    ChangeOrder,
    DrawingPdf,
    JointType,
    Material,
    Origin,
    Photo,
    Role,
    Scenario,
    Spec,
    SpecSource,
    Status,
    WeldEvent,
    generate_id,
)
from weld_codec import WeldScheme, assign_event
from weld_lookup import WeldLookup


class ChangeOrderBuilder:
    """Build and validate ChangeOrder objects without UI or filesystem side effects."""

    def __init__(self, lookup=None, scheme=None, clock=None):
        self.lookup = lookup if lookup is not None else WeldLookup()
        self.scheme = scheme if scheme is not None else WeldScheme()
        self.clock = clock if clock is not None else datetime.now

    def start(self, series, date, *, scenario=Scenario.NORMAL, dwg_no=None) -> ChangeOrder:
        co = ChangeOrder(
            status=Status.DRAFT,
            date=_clean(date),
            series=_clean(series),
            dwg_no=_clean(dwg_no) or self._lookup_dwg_no(series),
            scenario=scenario,
        )
        self._record(co, "created")
        return co

    def add_existing_weld(
        self,
        co: ChangeOrder,
        base,
        op,
        *,
        joint_type=JointType.WELD,
    ) -> WeldEvent:
        spec = self.lookup.lookup_spec(co.series, base) if self.lookup is not None else None
        spec_source = SpecSource.LOOKED_UP if spec is not None else SpecSource.MANUAL
        event = WeldEvent(
            joint_type=joint_type,
            origin=Origin.EXISTING,
            base=_clean(base),
            op=op,
            spec=spec if spec is not None else Spec(),
            spec_source=spec_source,
        )
        assigned = assign_event(event, self._existing_ids(co), scheme=self.scheme)
        co.welds.append(assigned)
        return assigned

    def add_new_weld(
        self,
        co: ChangeOrder,
        op,
        spec,
        *,
        joint_type=JointType.WELD,
    ) -> WeldEvent:
        event = WeldEvent(
            joint_type=joint_type,
            origin=Origin.NEW,
            op=op,
            spec=_coerce_spec(spec),
            spec_source=SpecSource.MANUAL,
        )
        assigned = assign_event(
            event,
            self._existing_ids(co),
            exists=lambda code: self.lookup.exists(co.series, code) if self.lookup is not None else False,
            scheme=self.scheme,
        )
        co.welds.append(assigned)
        return assigned

    def add_photo(self, co: ChangeOrder, role, file, *, weld_ref=None) -> Photo:
        photo = Photo(role=role, file=_clean(file), weld_ref=_clean(weld_ref))
        co.photos.append(photo)
        return photo

    def set_drawing_pdf(self, co: ChangeOrder, file) -> None:
        co.drawing_pdf = DrawingPdf(file=_clean(file))

    def set_reason(self, co: ChangeOrder, text) -> None:
        co.reason = _clean(text)

    def add_material(self, co: ChangeOrder, **fields) -> Material:
        material = Material(**fields)
        co.materials.append(material)
        return material

    def set_authorization(self, co: ChangeOrder, **fields) -> None:
        co.authorization = Authorization(**fields)

    def validate(self, co: ChangeOrder, *, required=None) -> list[dict]:
        issues: list[dict] = []
        if not _has_photo(co, Role.BEFORE):
            issues.append(_issue("missing_before_photo", "photos.before", "before photo is required"))
        if not _has_photo(co, Role.AFTER):
            issues.append(_issue("missing_after_photo", "photos.after", "after photo is required"))
        if co.drawing_pdf is None or not _clean(co.drawing_pdf.file):
            issues.append(_issue("missing_drawing_pdf", "drawing_pdf.file", "drawing PDF is required"))

        for key in required or []:
            normalized = str(key).strip()
            if normalized in {"materials", "material"} and not co.materials:
                issues.append(_issue("missing_materials", "materials", "materials are required"))
            elif normalized in {"authorization", "approval"} and co.authorization is None:
                issues.append(_issue("missing_authorization", "authorization", "authorization is required"))
            elif normalized == "reason" and not _clean(co.reason):
                issues.append(_issue("missing_reason", "reason", "reason is required"))
            elif normalized == "welds" and not co.welds:
                issues.append(_issue("missing_welds", "welds", "at least one weld event is required"))
        return issues

    def compute_status(self, co: ChangeOrder, *, required=None) -> Status:
        status = Status.COMPLETE if not self.validate(co, required=required) else Status.PARTIAL
        co.status = status
        return status

    def finalize_id(self, co: ChangeOrder, existing_ids: Iterable[str]) -> ChangeOrder:
        co.id = generate_id(co.series or "", co.date or "", existing_ids)
        return co

    def _existing_ids(self, co: ChangeOrder) -> list[str]:
        ids: list[str] = []
        if self.lookup is not None:
            ids.extend(self.lookup.existing_weld_ids(co.series))
        ids.extend(w.code for w in co.welds if _clean(w.code))
        return [str(weld_id) for weld_id in ids]

    def _lookup_dwg_no(self, series) -> str | None:
        for name in ("lookup_dwg_no", "get_dwg_no", "dwg_no_for_series"):
            method = getattr(self.lookup, name, None)
            if callable(method):
                try:
                    return _clean(method(series))
                except Exception:
                    return None
        return None

    def _record(self, co: ChangeOrder, action: str, detail: Any = None) -> AuditEntry:
        entry = AuditEntry(when=self._now_iso(), action=action, detail=detail)
        co.audit.history.append(entry)
        return entry

    def _now_iso(self) -> str:
        value = self.clock()
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_spec(spec) -> Spec:
    if spec is None:
        return Spec()
    if isinstance(spec, Spec):
        return spec
    if isinstance(spec, dict):
        return Spec.from_dict(spec)
    raise TypeError("spec must be a Spec, dict, or None")


def _enum_value(value) -> Any:
    return value.value if hasattr(value, "value") else value


def _has_photo(co: ChangeOrder, role: Role) -> bool:
    role_value = _enum_value(role)
    return any(_enum_value(photo.role) == role_value and _clean(photo.file) for photo in co.photos)


def _issue(code: str, field: str, message: str) -> dict:
    return {"code": code, "field": field, "message": message}


__all__ = ["ChangeOrderBuilder"]
