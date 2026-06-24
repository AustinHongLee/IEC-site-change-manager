# -*- coding: utf-8 -*-
"""Headless persistence/export service for ChangeOrder records."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from change_order import ChangeOrder, Role


@dataclass
class ExportResult:
    folder: Path
    record_path: Path
    copied: list[tuple[str, str]]
    missing: list[str]


def export_change_order(co, attachments_root, *, overwrite: bool = False) -> ExportResult:
    """Export a ChangeOrder folder with copied attachments and relative file refs."""
    if co.id is None or str(co.id).strip() == "":
        raise ValueError("ChangeOrder id is required before export")

    root = Path(attachments_root)
    folder = root / str(co.id)
    record_path = folder / "change_order.json"
    if record_path.exists() and not overwrite:
        raise FileExistsError(f"ChangeOrder record already exists: {record_path}")

    folder.mkdir(parents=True, exist_ok=True)
    exported = ChangeOrder.from_dict(co.to_dict())
    copied: list[tuple[str, str]] = []
    missing: list[str] = []

    role_counts: dict[str, int] = {}
    for photo in exported.photos:
        source = _source_path(photo.file)
        if source is None:
            continue
        role_key = _role_key(photo.role)
        role_counts[role_key] = role_counts.get(role_key, 0) + 1
        relative_name = f"{role_key}_{role_counts[role_key]}{source.suffix}"
        if _copy_if_exists(source, folder / relative_name, copied, missing):
            photo.file = relative_name

    if exported.drawing_pdf is not None:
        source = _source_path(exported.drawing_pdf.file)
        if source is not None and _copy_if_exists(source, folder / "drawing.pdf", copied, missing):
            exported.drawing_pdf.file = "drawing.pdf"

    exported.save_json(record_path)
    return ExportResult(folder=folder, record_path=record_path, copied=copied, missing=missing)


def _source_path(value) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    return Path(text) if text else None


def _copy_if_exists(source: Path, destination: Path, copied: list[tuple[str, str]], missing: list[str]) -> bool:
    if not source.exists():
        missing.append(str(source))
        return False
    shutil.copy2(source, destination)
    copied.append((str(source), destination.name))
    return True


def _role_key(role) -> str:
    value = role.value if hasattr(role, "value") else role
    if value == Role.AFTER.value:
        return "after"
    return "before"


__all__ = ["ExportResult", "export_change_order"]
