# -*- coding: utf-8 -*-
"""Read-only support bundle collection for field troubleshooting."""

from __future__ import annotations

import json
import os
import platform
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app_info import APP_CHANNEL, APP_ID, APP_LOCAL_NAME, APP_NAME, APP_VERSION, format_app_identity
from config import RESOURCE_DIR, TEMPLATE_PATH_6, TEMPLATE_PATH_27
from integrity_audit import audit_integrity, format_integrity_report
from material_constants import WIZARD_DATA_PATH
from output_capabilities import build_output_capability_report
from project_guard import build_startup_decision, format_guard_report, inspect_project
from resources import resource_path


def _issue_to_dict(issue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "title": getattr(issue, "title", ""),
        "message": issue.message,
        "path": getattr(issue, "path", ""),
        "refs": list(getattr(issue, "refs", []) or []),
        "auto_fixable": getattr(issue, "auto_fixable", False),
    }


def _default_output_dir(project_root: Path) -> Path:
    return project_root / "staging" / "support_bundle"


def _collect_log_excerpts(
    project_root: Path,
    *,
    max_files: int = 3,
    max_bytes: int = 512 * 1024,
) -> list[tuple[str, str]]:
    """收集最新幾個 log 檔的尾段，給現場故障回報用（唯讀，不修改原檔）。"""
    logs_dir = project_root / "logs"
    if not logs_dir.is_dir():
        return []
    candidates = sorted(
        (p for p in logs_dir.glob("*.log*") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:max_files]
    excerpts: list[tuple[str, str]] = []
    for path in candidates:
        try:
            size = path.stat().st_size
            with path.open("rb") as handle:
                if size > max_bytes:
                    handle.seek(-max_bytes, os.SEEK_END)
                raw = handle.read()
            text = raw.decode("utf-8", errors="replace")
            if size > max_bytes:
                text = f"（已截斷，僅保留最後 {max_bytes // 1024} KB）\n{text}"
            excerpts.append((f"logs/{path.name}", text))
        except OSError as exc:
            excerpts.append((f"logs/{path.name}.read_error.txt", f"無法讀取此日誌：{exc}"))
    return excerpts


def collect_support_bundle(
    project_root: str | Path,
    *,
    output_dir: str | Path | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    created_at = timestamp or datetime.now()
    stamp = created_at.strftime("%Y%m%d_%H%M%S")
    output = Path(output_dir).resolve() if output_dir else _default_output_dir(root)
    zip_path = output / f"support_bundle_{stamp}.zip"

    guard = inspect_project(root)
    decision = build_startup_decision(guard)
    integrity = audit_integrity(root)
    capability = build_output_capability_report(
        probe_com_application=False,
        probe_libreoffice_version=False,
    )

    diagnostics = {
        "schema_version": "support_bundle.v1",
        "created_at": created_at.isoformat(timespec="seconds"),
        "app": {
            "id": APP_ID,
            "name": APP_NAME,
            "local_name": APP_LOCAL_NAME,
            "version": APP_VERSION,
            "channel": APP_CHANNEL,
            "identity": format_app_identity(),
            "paths": {
                "resource_dir": RESOURCE_DIR,
                "template_path_6": TEMPLATE_PATH_6,
                "template_6_exists": Path(TEMPLATE_PATH_6).is_file(),
                "template_path_27": TEMPLATE_PATH_27,
                "template_27_exists": Path(TEMPLATE_PATH_27).is_file(),
                "wizard_data_path": WIZARD_DATA_PATH,
                "wizard_data_exists": Path(WIZARD_DATA_PATH).is_file(),
                "material_pricebook_seed_path": resource_path("material_pricebook_seed.json"),
                "material_pricebook_seed_exists": Path(resource_path("material_pricebook_seed.json")).is_file(),
            },
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
            "computer": os.environ.get("COMPUTERNAME") or platform.node(),
        },
        "project": {
            "root": str(root),
            "startup": {
                "state": guard.state,
                "decision": {
                    "action": decision.action,
                    "title": decision.title,
                    "can_continue": decision.can_continue,
                    "can_auto_repair": decision.can_auto_repair,
                    "blocking_codes": decision.blocking_codes,
                    "repairable_codes": decision.repairable_codes,
                },
                "issues": [_issue_to_dict(issue) for issue in guard.issues],
            },
            "integrity": {
                "has_errors": integrity.has_errors,
                "counts": integrity.counts,
                "severity": integrity.count_by_severity(),
                "issues": [_issue_to_dict(issue) for issue in integrity.issues],
            },
        },
        "output_capabilities": capability,
    }
    health_text = "\n\n".join(
        [
            format_app_identity(),
            format_guard_report(guard),
            format_integrity_report(integrity, max_refs=40),
        ]
    )

    log_excerpts = _collect_log_excerpts(root)

    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("diagnostics.json", json.dumps(diagnostics, ensure_ascii=False, indent=2))
        bundle.writestr("health_check.txt", health_text)
        for arcname, content in log_excerpts:
            bundle.writestr(arcname, content)

    return {
        "ok": True,
        "bundle_path": str(zip_path),
        "project_root": str(root),
        "startup_action": decision.action,
        "integrity_severity": integrity.count_by_severity(),
        "logs_included": len(log_excerpts),
    }
