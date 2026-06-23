# -*- coding: utf-8 -*-
"""
project_guard.py - 專案資料夾守門與單寫者鎖

這個模組只處理啟動前的低階安全檢查：
- 必要資料夾與設定檔是否存在
- records/billing JSON 是否可讀
- 可安全修復的空資料夾與預設檔案
- 單寫者 lock + heartbeat
"""

from __future__ import annotations

import atexit
import ctypes
import copy
import getpass
import json
import os
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from operation_journal import list_pending_journals


REQUIRED_DIRS = ("attachments", "records", "output", "pdf", "staging", "logs")
REQUIRED_FILES = ("settings.json",)
PROJECT_MARKER = ".project.json"
LOCK_FILE = ".project.lock"
BOOTSTRAP_REPAIR_CODES = {
    "first_open",
    "missing_settings",
    *(f"missing_dir_{dirname}" for dirname in REQUIRED_DIRS),
}
RUNTIME_ARTIFACT_NAMES = {"IEC-site-change-manager.exe", "_internal"}
DISTRIBUTION_ARTIFACT_NAMES = {
    "README.md",
    "README.txt",
    "使用說明.md",
    "使用說明.txt",
    "啟動工務修改單.bat",
    "啟動工務修改單.cmd",
    "LibreOffice",
}


def _name_matches(name: str, allowed: set[str]) -> bool:
    normalized = name.casefold()
    return any(normalized == item.casefold() for item in allowed)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def atomic_write_json(path: str | Path, data: dict[str, Any]) -> None:
    """原子寫入 JSON，避免中斷時留下半個檔案。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, target)


def safe_load_json(path: str | Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None, "JSON 根節點不是物件"
        return data, None
    except Exception as exc:
        return None, str(exc)


@dataclass
class ProjectIssue:
    severity: str
    code: str
    title: str
    message: str
    path: str = ""
    auto_fixable: bool = False


@dataclass
class GuardResult:
    root: str
    state: str
    issues: list[ProjectIssue] = field(default_factory=list)
    repaired: list[str] = field(default_factory=list)

    @property
    def blocking_issues(self) -> list[ProjectIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def has_blocking_issues(self) -> bool:
        return bool(self.blocking_issues)

    @property
    def auto_fixable_issues(self) -> list[ProjectIssue]:
        return [i for i in self.issues if i.auto_fixable]

    @property
    def can_auto_repair(self) -> bool:
        return bool(self.auto_fixable_issues) and not self.has_blocking_issues

    @property
    def is_healthy(self) -> bool:
        return self.state == "healthy" and not self.issues


@dataclass(frozen=True)
class StartupDecision:
    action: str
    title: str
    message: str
    can_continue: bool
    can_auto_repair: bool
    blocking_codes: list[str] = field(default_factory=list)
    repairable_codes: list[str] = field(default_factory=list)


def build_startup_decision(result: GuardResult) -> StartupDecision:
    blocking_codes = [issue.code for issue in result.blocking_issues]
    repairable_codes = [issue.code for issue in result.auto_fixable_issues]

    if result.has_blocking_issues:
        if "possible_wrong_folder" in blocking_codes:
            return StartupDecision(
                action="blocked_wrong_folder",
                title="可能跑錯資料夾",
                message="目前位置不像工務修改單專案。為避免把資料夾結構寫到錯誤位置，啟動已停止。",
                can_continue=False,
                can_auto_repair=False,
                blocking_codes=blocking_codes,
                repairable_codes=repairable_codes,
            )
        if "missing_records_json" in blocking_codes:
            return StartupDecision(
                action="blocked_possible_deleted_records",
                title="疑似 records.json 遺失",
                message="attachments/ 已有資料，但主紀錄 records.json 不存在。這可能是誤刪，需人工確認後再修復。",
                can_continue=False,
                can_auto_repair=False,
                blocking_codes=blocking_codes,
                repairable_codes=repairable_codes,
            )
        return StartupDecision(
            action="blocked",
            title="啟動前需要人工處理",
            message="專案資料存在阻擋性問題，程式不會自動覆蓋或修復。",
            can_continue=False,
            can_auto_repair=False,
            blocking_codes=blocking_codes,
            repairable_codes=repairable_codes,
        )

    bootstrap_only = all(code in BOOTSTRAP_REPAIR_CODES for code in repairable_codes)
    if result.state == "first_open" and result.can_auto_repair and bootstrap_only:
        return StartupDecision(
            action="initialize",
            title="第一次開啟專案",
            message="此資料夾尚未初始化，可建立必要資料夾與預設設定後啟動。",
            can_continue=True,
            can_auto_repair=True,
            blocking_codes=blocking_codes,
            repairable_codes=repairable_codes,
        )

    if result.can_auto_repair:
        return StartupDecision(
            action="repair",
            title="專案結構可自動修復",
            message="偵測到缺少空資料夾或預設資料檔，可安全補建後啟動。",
            can_continue=True,
            can_auto_repair=True,
            blocking_codes=blocking_codes,
            repairable_codes=repairable_codes,
        )

    if result.issues:
        return StartupDecision(
            action="review",
            title="專案需要人工確認",
            message="專案可讀，但仍有不適合自動修復的提醒，建議先到健康檢查確認。",
            can_continue=True,
            can_auto_repair=False,
            blocking_codes=blocking_codes,
            repairable_codes=repairable_codes,
        )

    return StartupDecision(
        action="healthy",
        title="專案狀態正常",
        message="必要資料夾與設定檔已就緒。",
        can_continue=True,
        can_auto_repair=False,
        blocking_codes=blocking_codes,
        repairable_codes=repairable_codes,
    )


def _default_settings() -> dict[str, Any]:
    try:
        from settings_manager import DEFAULT_SETTINGS
        return copy.deepcopy(DEFAULT_SETTINGS)
    except Exception:
        return {
            "paths": {
                "drawing_list": "",
                "attachments_root": "",
                "output_root": "",
                "pdf_output": "",
                "last_browse_dir": "",
                "weld_control_table": "",
                "prefab_drawing_dir": "",
            },
            "runtime": {
                "export_pdf": True,
                "skip_unchanged": True,
                "debug_mode": False,
                "auto_preprocess_images": True,
                "preprocess_max_edge": 1280,
                "preprocess_quality": 85,
            },
            "meta": {"version": "1.2", "last_modified": ""},
        }


def _default_project_marker(root: Path) -> dict[str, Any]:
    return {
        "app": "IEC Site Change Manager",
        "schema_version": 1,
        "project_name": root.name,
        "created_at": now_iso(),
    }


def _default_records() -> dict[str, Any]:
    return {
        "records": [],
        "details": [],
        "materials": [],
        "meta": {
            "version": "2.0",
            "created_at": now_iso(),
            "last_modified": now_iso(),
        },
    }


def _default_billing() -> dict[str, Any]:
    return {
        "billing": {},
        "meta": {
            "version": "1.0",
            "created_at": now_iso(),
            "last_modified": now_iso(),
        },
    }


def _default_billing_batches() -> dict[str, Any]:
    return {
        "batches": [],
        "meta": {
            "version": "1.0",
            "currency": "TWD",
            "tax_mode": "exclusive",
            "tax_rate": "5%",
            "rounding_rule": "TWD_HALF_UP",
            "created_at": now_iso(),
            "last_modified": now_iso(),
        },
    }


def _default_material_pricebook() -> dict[str, Any]:
    return {
        "items": [],
        "history": [],
        "meta": {
            "version": "1.1",
            "currency": "TWD",
            "notes": "空白價目表；可逐步加入專案合約材料單價。",
            "created_at": now_iso(),
            "last_modified": now_iso(),
        },
    }


def _default_dwg_map() -> dict[str, Any]:
    return {
        "source": "",
        "source_mtime": 0,
        "updated": now_iso(),
        "count": 0,
        "mapping": {},
    }


def _has_attachment_folders(root: Path) -> bool:
    attachments = root / "attachments"
    if not attachments.is_dir():
        return False
    for date_dir in attachments.iterdir():
        if date_dir.is_dir() and date_dir.name.isdigit() and len(date_dir.name) == 8:
            return True
    return False


def _looks_empty_project_root(root: Path) -> bool:
    known = set(REQUIRED_DIRS) | {PROJECT_MARKER, "settings.json"}
    try:
        names = [p.name for p in root.iterdir() if not p.name.startswith(".git")]
    except OSError:
        return False
    has_runtime_artifact = any(_name_matches(name, RUNTIME_ARTIFACT_NAMES) for name in names)
    visible = []
    for name in names:
        if _name_matches(name, RUNTIME_ARTIFACT_NAMES):
            continue
        if has_runtime_artifact and _name_matches(name, DISTRIBUTION_ARTIFACT_NAMES):
            continue
        visible.append(name)
    return not visible or all(name in known for name in visible)


def inspect_project(project_root: str | Path) -> GuardResult:
    root = Path(project_root).resolve()
    issues: list[ProjectIssue] = []

    if not root.exists():
        return GuardResult(
            root=str(root),
            state="damaged",
            issues=[
                ProjectIssue(
                    "error",
                    "root_missing",
                    "專案資料夾不存在",
                    "目前指定的專案資料夾不存在，無法啟動。",
                    str(root),
                    False,
                )
            ],
        )

    marker_exists = (root / PROJECT_MARKER).exists()
    has_any_required_dir = any((root / name).is_dir() for name in REQUIRED_DIRS)
    has_settings = (root / "settings.json").exists()
    first_open = not marker_exists and not has_any_required_dir and not has_settings
    looks_empty = _looks_empty_project_root(root)

    if first_open and not looks_empty:
        issues.append(ProjectIssue(
            "error",
            "possible_wrong_folder",
            "可能跑錯資料夾",
            "這個資料夾不是空的，也沒有任何專案結構。為避免污染錯誤位置，請先確認路徑。",
            str(root),
            False,
        ))
    elif first_open or looks_empty and not marker_exists:
        issues.append(ProjectIssue(
            "info",
            "first_open",
            "第一次開啟專案",
            "這個資料夾尚未初始化，可建立必要資料夾與預設設定。",
            str(root),
            True,
        ))
    elif not marker_exists:
        issues.append(ProjectIssue(
            "warning",
            "missing_project_marker",
            "缺少專案識別檔",
            "此資料夾看起來像專案，但缺少 .project.json。可補建識別檔。",
            str(root / PROJECT_MARKER),
            True,
        ))

    pending_journals = list_pending_journals(root)
    if pending_journals:
        issues.append(ProjectIssue(
            "error",
            "pending_operation_journal",
            "有未完成的多檔操作",
            "偵測到上次操作可能中途中斷。請先檢查 journal 內容與資料狀態。",
            "\n".join(pending_journals),
            False,
        ))

    for dirname in REQUIRED_DIRS:
        path = root / dirname
        if not path.is_dir():
            issues.append(ProjectIssue(
                "warning",
                f"missing_dir_{dirname}",
                f"缺少 {dirname}/",
                "必要資料夾不存在。空資料夾可安全重建。",
                str(path),
                True,
            ))

    settings_path = root / "settings.json"
    if not settings_path.exists():
        issues.append(ProjectIssue(
            "warning",
            "missing_settings",
            "缺少 settings.json",
            "設定檔不存在。可用預設值重建，但路徑設定需要使用者重新確認。",
            str(settings_path),
            True,
        ))
    else:
        data, error = safe_load_json(settings_path)
        if error:
            issues.append(ProjectIssue(
                "error",
                "settings_invalid_json",
                "settings.json 無法讀取",
                f"設定檔 JSON 損壞或格式錯誤：{error}",
                str(settings_path),
                False,
            ))
        elif "paths" not in data:
            issues.append(ProjectIssue(
                "warning",
                "settings_missing_paths",
                "settings.json 缺少 paths 區段",
                "設定檔可讀，但缺少新版必要欄位。後續可由設定管理器補齊。",
                str(settings_path),
                False,
            ))

    records_path = root / "records" / "records.json"
    billing_path = root / "records" / "billing.json"
    billing_batches_path = root / "records" / "billing_batches.json"
    pricebook_path = root / "records" / "material_pricebook.json"
    dwg_map_path = root / "records" / "dwg_map.json"

    if records_path.exists():
        store, error = safe_load_json(records_path)
        if error:
            issues.append(ProjectIssue(
                "error",
                "records_invalid_json",
                "records.json 無法讀取",
                f"主紀錄檔 JSON 損壞或格式錯誤：{error}",
                str(records_path),
                False,
            ))
        else:
            for key in ("records", "details", "materials"):
                if not isinstance(store.get(key), list):
                    issues.append(ProjectIssue(
                        "warning",
                        f"records_missing_{key}",
                        f"records.json 缺少 {key}",
                        "主紀錄檔缺少必要清單欄位，需進行 schema 修補。",
                        str(records_path),
                        True,
                    ))
    elif (root / "records").exists():
        auto_fixable = not _has_attachment_folders(root)
        issues.append(ProjectIssue(
            "warning" if auto_fixable else "error",
            "missing_records_json",
            "缺少 records.json",
            "主紀錄檔不存在。若 attachments 已有資料，需人工確認是否為誤刪。",
            str(records_path),
            auto_fixable,
        ))

    if billing_path.exists():
        data, error = safe_load_json(billing_path)
        if error:
            issues.append(ProjectIssue(
                "error",
                "billing_invalid_json",
                "billing.json 無法讀取",
                f"請款資料 JSON 損壞或格式錯誤：{error}",
                str(billing_path),
                False,
            ))
        elif not isinstance(data.get("billing"), dict):
            issues.append(ProjectIssue(
                "warning",
                "billing_missing_root",
                "billing.json 缺少 billing 物件",
                "請款資料可讀，但缺少必要根節點。",
                str(billing_path),
                True,
            ))
    elif (root / "records").exists():
        issues.append(ProjectIssue(
            "warning",
            "missing_billing_json",
            "缺少 billing.json",
            "請款資料檔不存在。可建立空白請款資料檔。",
            str(billing_path),
            True,
        ))

    if billing_batches_path.exists():
        data, error = safe_load_json(billing_batches_path)
        if error:
            issues.append(ProjectIssue(
                "error",
                "billing_batches_invalid_json",
                "billing_batches.json 無法讀取",
                f"請款批次資料 JSON 損壞或格式錯誤：{error}",
                str(billing_batches_path),
                False,
            ))
        elif not isinstance(data.get("batches"), list):
            issues.append(ProjectIssue(
                "warning",
                "billing_batches_missing_root",
                "billing_batches.json 缺少 batches 清單",
                "請款批次資料可讀，但缺少必要根節點。",
                str(billing_batches_path),
                True,
            ))
        else:
            try:
                from billing_batch import validate_billing_batches
                batch_issues = validate_billing_batches(data)
            except Exception:
                batch_issues = []
            for batch_issue in batch_issues:
                severity = "error" if batch_issue.code == "duplicate_active_report" else "warning"
                issues.append(ProjectIssue(
                    severity,
                    f"billing_batch_{batch_issue.code}",
                    "請款批次資料異常",
                    batch_issue.message,
                    str(billing_batches_path),
                    False,
                ))
    elif (root / "records").exists():
        issues.append(ProjectIssue(
            "warning",
            "missing_billing_batches_json",
            "缺少 billing_batches.json",
            "請款批次資料檔不存在。可建立空白批次資料檔。",
            str(billing_batches_path),
            True,
        ))

    if pricebook_path.exists():
        data, error = safe_load_json(pricebook_path)
        if error:
            issues.append(ProjectIssue(
                "warning",
                "material_pricebook_invalid_json",
                "material_pricebook.json 無法讀取",
                f"材料價目表 JSON 損壞或格式錯誤：{error}",
                str(pricebook_path),
                False,
            ))
        elif not isinstance(data.get("items"), list):
            issues.append(ProjectIssue(
                "warning",
                "material_pricebook_missing_items",
                "material_pricebook.json 缺少 items 清單",
                "材料價目表可讀，但缺少必要清單欄位。",
                str(pricebook_path),
                True,
            ))
    elif (root / "records").exists():
        issues.append(ProjectIssue(
            "warning",
            "missing_material_pricebook_json",
            "缺少 material_pricebook.json",
            "材料價目表不存在。可建立空白價目表；不影響既有資料。",
            str(pricebook_path),
            True,
        ))

    if dwg_map_path.exists():
        _, error = safe_load_json(dwg_map_path)
        if error:
            issues.append(ProjectIssue(
                "warning",
                "dwg_map_invalid_json",
                "dwg_map.json 無法讀取",
                "DWG 快取損壞，可在下次讀取 DWG LIST 時重建。",
                str(dwg_map_path),
                False,
            ))

    snapshot_path = root / "records" / "weld_snapshot.json"
    if snapshot_path.exists():
        snapshot, error = safe_load_json(snapshot_path)
        if error:
            issues.append(ProjectIssue(
                "warning",
                "weld_snapshot_invalid_json",
                "weld_snapshot.json 無法讀取",
                "焊口快照損壞，可重新建立，不影響主紀錄。",
                str(snapshot_path),
                False,
            ))
        else:
            attachments_root = snapshot.get("attachments_root", "")
            if attachments_root and os.path.isabs(str(attachments_root)):
                try:
                    expected = str((root / "attachments").resolve())
                    actual = str(Path(str(attachments_root)).resolve())
                    if actual == expected:
                        issues.append(ProjectIssue(
                            "warning",
                            "snapshot_absolute_path",
                            "weld_snapshot.json 含本機絕對路徑",
                            "快照內的 attachments_root 可改成相對路徑，提升換機可攜性。",
                            str(snapshot_path),
                            True,
                        ))
                except OSError:
                    pass

    state = "healthy"
    if any(i.severity == "error" for i in issues):
        state = "damaged"
    elif any(i.code == "first_open" for i in issues):
        state = "first_open"
    elif issues:
        state = "needs_repair"

    return GuardResult(root=str(root), state=state, issues=issues)


def repair_project(project_root: str | Path) -> GuardResult:
    root = Path(project_root).resolve()
    before = inspect_project(root)
    repaired: list[str] = []

    if before.has_blocking_issues:
        before.repaired = repaired
        return before

    root.mkdir(parents=True, exist_ok=True)
    for dirname in REQUIRED_DIRS:
        path = root / dirname
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            repaired.append(f"建立 {dirname}/")

    marker_path = root / PROJECT_MARKER
    if not marker_path.exists():
        atomic_write_json(marker_path, _default_project_marker(root))
        repaired.append("建立 .project.json")

    settings_path = root / "settings.json"
    if not settings_path.exists():
        settings = _default_settings()
        settings.setdefault("meta", {})["last_modified"] = now_iso()
        atomic_write_json(settings_path, settings)
        repaired.append("建立 settings.json")

    records_path = root / "records" / "records.json"
    if not records_path.exists() and not _has_attachment_folders(root):
        atomic_write_json(records_path, _default_records())
        repaired.append("建立 records/records.json")

    billing_path = root / "records" / "billing.json"
    if not billing_path.exists():
        atomic_write_json(billing_path, _default_billing())
        repaired.append("建立 records/billing.json")

    billing_batches_path = root / "records" / "billing_batches.json"
    if not billing_batches_path.exists():
        atomic_write_json(billing_batches_path, _default_billing_batches())
        repaired.append("建立 records/billing_batches.json")
    else:
        batch_data, batch_error = safe_load_json(billing_batches_path)
        if not batch_error and isinstance(batch_data, dict) and not isinstance(batch_data.get("batches"), list):
            batch_data["batches"] = []
            batch_data.setdefault("meta", _default_billing_batches()["meta"])
            atomic_write_json(billing_batches_path, batch_data)
            repaired.append("修補 records/billing_batches.json batches")

    pricebook_path = root / "records" / "material_pricebook.json"
    if not pricebook_path.exists():
        atomic_write_json(pricebook_path, _default_material_pricebook())
        repaired.append("建立 records/material_pricebook.json")
    else:
        pricebook, error = safe_load_json(pricebook_path)
        if not error and pricebook is not None and not isinstance(pricebook.get("items"), list):
            pricebook["items"] = []
            pricebook.setdefault("meta", {})
            pricebook["meta"]["last_modified"] = now_iso()
            atomic_write_json(pricebook_path, pricebook)
            repaired.append("修補 records/material_pricebook.json items")

    dwg_map_path = root / "records" / "dwg_map.json"
    if not dwg_map_path.exists():
        atomic_write_json(dwg_map_path, _default_dwg_map())
        repaired.append("建立 records/dwg_map.json")

    snapshot_path = root / "records" / "weld_snapshot.json"
    if snapshot_path.exists():
        snapshot, error = safe_load_json(snapshot_path)
        if not error and snapshot:
            attachments_root = snapshot.get("attachments_root", "")
            if attachments_root and os.path.isabs(str(attachments_root)):
                try:
                    expected = str((root / "attachments").resolve())
                    actual = str(Path(str(attachments_root)).resolve())
                    if actual == expected:
                        snapshot["attachments_root"] = "attachments"
                        atomic_write_json(snapshot_path, snapshot)
                        repaired.append("weld_snapshot.json 改為相對路徑")
                except OSError:
                    pass

    after = inspect_project(root)
    after.repaired = repaired
    return after


def format_guard_report(result: GuardResult) -> str:
    decision = build_startup_decision(result)
    lines = [
        f"專案資料夾: {result.root}",
        f"狀態: {result.state}",
        f"啟動判斷: {decision.title}",
    ]
    if result.repaired:
        lines.append("")
        lines.append("已修復:")
        for item in result.repaired:
            lines.append(f"- {item}")
    if result.issues:
        lines.append("")
        lines.append("檢查結果:")
        for issue in result.issues:
            tag = issue.severity.upper()
            lines.append(f"- [{tag}] {issue.title}: {issue.message}")
            if issue.path:
                lines.append(f"  path: {issue.path}")
    else:
        lines.append("")
        lines.append("檢查結果: 正常")
    return "\n".join(lines)


def _windows_process_exists(pid: int) -> bool:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


class ProjectLock:
    """以 lock file 實作單寫者鎖。"""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_age_seconds: int = 1800,
        heartbeat_interval: int = 10,
    ):
        self.root = Path(project_root).resolve()
        self.lock_path = self.root / LOCK_FILE
        self.max_age_seconds = max_age_seconds
        self.heartbeat_interval = heartbeat_interval
        self.token: str | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _lock_payload(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "pid": os.getpid(),
            "user": getpass.getuser(),
            "host": socket.gethostname(),
            "created_at": now_iso(),
            "heartbeat_at": now_iso(),
        }

    def read_existing(self) -> dict[str, Any] | None:
        data, error = safe_load_json(self.lock_path)
        if error:
            return None
        return data

    def _is_stale(self) -> bool:
        info = self.read_existing()
        if not info:
            try:
                age = time.time() - self.lock_path.stat().st_mtime
                return age > self.max_age_seconds
            except OSError:
                return True

        if self._same_local_owner(info) and not self._lock_process_exists(info):
            return True

        heartbeat = info.get("heartbeat_at") or info.get("created_at")
        if not heartbeat:
            return False
        try:
            dt = datetime.fromisoformat(str(heartbeat))
        except ValueError:
            return False
        return datetime.now() - dt > timedelta(seconds=self.max_age_seconds)

    def _same_local_owner(self, info: dict[str, Any]) -> bool:
        return (
            str(info.get("host", "")).strip().lower() == socket.gethostname().lower()
            and str(info.get("user", "")).strip().lower() == getpass.getuser().lower()
        )

    @staticmethod
    def _lock_process_exists(info: dict[str, Any]) -> bool:
        try:
            pid = int(info.get("pid", 0))
        except (TypeError, ValueError):
            return True
        if pid <= 0:
            return False
        if os.name == "nt":
            return _windows_process_exists(pid)
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError as exc:
            if getattr(exc, "winerror", None) in (87, 1168):
                return False
            return True

    def acquire(self, *, start_heartbeat: bool = True) -> bool:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            if not self._is_stale():
                return False
            try:
                self.lock_path.unlink()
            except OSError:
                return False

        self.token = str(uuid.uuid4())
        payload = self._lock_payload()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(str(self.lock_path), flags)
        except FileExistsError:
            self.token = None
            return False

        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")

        if start_heartbeat:
            self.start_heartbeat()
        atexit.register(self.release)
        return True

    def refresh(self) -> bool:
        if not self.token:
            return False
        info = self.read_existing()
        if not info or info.get("token") != self.token:
            return False
        info["heartbeat_at"] = now_iso()
        atomic_write_json(self.lock_path, info)
        return True

    def start_heartbeat(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def run():
            while not self._stop_event.wait(self.heartbeat_interval):
                if not self.refresh():
                    break

        self._thread = threading.Thread(target=run, name="project-lock-heartbeat", daemon=True)
        self._thread.start()

    def release(self) -> None:
        self._stop_event.set()
        if not self.token:
            return
        info = self.read_existing()
        if info and info.get("token") == self.token:
            try:
                self.lock_path.unlink()
            except OSError:
                pass
        self.token = None

    def __enter__(self) -> "ProjectLock":
        if not self.acquire():
            raise RuntimeError("無法取得專案寫入鎖")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
