# -*- coding: utf-8 -*-
"""Shared output-result envelope helpers.

The envelope is intentionally small: detailed renderer-specific diagnostics can
stay beside it, while UI/batch/AI flows read the same top-level contract.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


OUTPUT_RESULT_SCHEMA_VERSION = "output_result.v1"


def output_item(
    *,
    kind: str,
    path: str | os.PathLike[str] | None,
    role: str = "primary",
    label: str = "",
    optional: bool = False,
) -> dict[str, Any]:
    text_path = "" if path is None else str(path)
    return {
        "kind": str(kind or "").strip(),
        "path": text_path,
        "role": str(role or "").strip() or "primary",
        "label": str(label or "").strip(),
        "optional": bool(optional),
        "exists": bool(text_path and Path(text_path).exists()),
    }


def step_item(
    *,
    key: str,
    ok: bool,
    label: str = "",
    detail: str = "",
) -> dict[str, Any]:
    return {
        "key": str(key or "").strip(),
        "ok": bool(ok),
        "label": str(label or "").strip(),
        "detail": str(detail or "").strip(),
    }


def build_output_result(
    *,
    ok: bool,
    outputs: list[dict[str, Any]] | None = None,
    issues: list[dict[str, Any]] | None = None,
    capabilities: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "result_schema_version": OUTPUT_RESULT_SCHEMA_VERSION,
        "ok": bool(ok),
        "outputs": dedupe_outputs(outputs or []),
        "issues": list(issues or []),
        "capabilities": capabilities or {},
        "steps": list(steps or []),
    }


def attach_output_envelope(
    result: dict[str, Any],
    *,
    outputs: list[dict[str, Any]] | None = None,
    capabilities: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result["result_schema_version"] = OUTPUT_RESULT_SCHEMA_VERSION
    result["outputs"] = dedupe_outputs(outputs or result.get("outputs", []) or [])
    result["capabilities"] = capabilities if capabilities is not None else result.get("capabilities", {})
    result["steps"] = list(steps if steps is not None else result.get("steps", []) or [])
    result["issues"] = list(result.get("issues", []) or [])
    result["ok"] = bool(result.get("ok"))
    return result


def dedupe_outputs(outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("kind", "")),
            str(item.get("path", "")),
            str(item.get("role", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(item))
    return result


def outputs_from_paths(*items: dict[str, Any]) -> list[dict[str, Any]]:
    return [output_item(**item) for item in items if item.get("path")]
