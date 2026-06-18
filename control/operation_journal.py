# -*- coding: utf-8 -*-
"""
operation_journal.py - 多檔操作 journal

多檔操作開始前建立 .journal，成功完成後刪除。若程式中途當機，
啟動守門可偵測殘留 journal，要求人工確認。
"""

from __future__ import annotations

import json
import os
import socket
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


JOURNAL_DIR = ".journals"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def list_pending_journals(project_root: str | Path) -> list[str]:
    journal_root = Path(project_root).resolve() / JOURNAL_DIR
    if not journal_root.is_dir():
        return []
    return sorted(str(path) for path in journal_root.glob("*.journal") if path.is_file())


class OperationJournal:
    """多檔操作的簡易 journal。"""

    def __init__(self, project_root: str | Path, operation: str, details: dict[str, Any] | None = None):
        self.project_root = Path(project_root).resolve()
        self.operation = operation
        self.details = details or {}
        self.journal_id = uuid.uuid4().hex
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in operation).strip("_")
        self.path = self.project_root / JOURNAL_DIR / f"{timestamp}_{safe_name}_{self.journal_id}.journal"
        self.data: dict[str, Any] = {}
        self.active = False

    def begin(self) -> "OperationJournal":
        self.data = {
            "id": self.journal_id,
            "operation": self.operation,
            "status": "started",
            "project_root": str(self.project_root),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "details": self.details,
            "steps": [],
        }
        _atomic_write(self.path, self.data)
        self.active = True
        return self

    def step(self, action: str, **payload: Any) -> None:
        if not self.active:
            return
        self.data.setdefault("steps", []).append({
            "at": _now_iso(),
            "action": action,
            "payload": payload,
        })
        self.data["updated_at"] = _now_iso()
        _atomic_write(self.path, self.data)

    def complete(self) -> None:
        if not self.active:
            return
        self.active = False
        try:
            self.path.unlink()
        except OSError:
            self.data["status"] = "completed"
            self.data["updated_at"] = _now_iso()
            _atomic_write(self.path, self.data)

    def fail(self, error: str) -> None:
        if not self.active:
            return
        self.active = False
        self.data["status"] = "failed"
        self.data["error"] = error
        self.data["updated_at"] = _now_iso()
        _atomic_write(self.path, self.data)

    def __enter__(self) -> "OperationJournal":
        return self.begin()

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.complete()
        else:
            self.fail(str(exc))
        return False
