# -*- coding: utf-8 -*-
"""
test_project_guard.py - 專案守門與單寫者鎖測試
"""

import json
import os
import getpass
import socket
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))


def test_repair_first_open_project(tmp_path):
    from project_guard import REQUIRED_DIRS, build_startup_decision, inspect_project, repair_project

    result = inspect_project(tmp_path)
    assert result.state == "first_open"
    assert result.can_auto_repair is True
    decision = build_startup_decision(result)
    assert decision.action == "initialize"
    assert decision.can_auto_repair is True

    repaired = repair_project(tmp_path)
    assert repaired.has_blocking_issues is False
    assert build_startup_decision(repaired).action == "healthy"
    for dirname in REQUIRED_DIRS:
        assert (tmp_path / dirname).is_dir()
    assert (tmp_path / ".project.json").exists()
    assert (tmp_path / "settings.json").exists()
    assert (tmp_path / "records" / "records.json").exists()
    assert (tmp_path / "records" / "billing.json").exists()
    assert (tmp_path / "records" / "billing_batches.json").exists()
    assert (tmp_path / "records" / "material_pricebook.json").exists()
    assert (tmp_path / "records" / "dwg_map.json").exists()


def test_records_missing_with_attachments_requires_review(tmp_path):
    from project_guard import build_startup_decision, inspect_project, repair_project

    (tmp_path / "attachments" / "20260101" / "001_1r1").mkdir(parents=True)
    (tmp_path / "records").mkdir()

    result = inspect_project(tmp_path)
    assert result.has_blocking_issues is True
    assert any(i.code == "missing_records_json" for i in result.issues)
    decision = build_startup_decision(result)
    assert decision.action == "blocked_possible_deleted_records"
    assert decision.can_continue is False

    repaired = repair_project(tmp_path)
    assert repaired.has_blocking_issues is True
    assert not (tmp_path / "records" / "records.json").exists()


def test_non_empty_unrecognized_folder_is_not_auto_repaired(tmp_path):
    from project_guard import build_startup_decision, inspect_project, repair_project

    (tmp_path / "random_document.txt").write_text("not a project", encoding="utf-8")

    result = inspect_project(tmp_path)
    assert result.has_blocking_issues is True
    assert any(i.code == "possible_wrong_folder" for i in result.issues)
    assert result.can_auto_repair is False
    decision = build_startup_decision(result)
    assert decision.action == "blocked_wrong_folder"

    repair_project(tmp_path)
    assert not (tmp_path / "attachments").exists()
    assert not (tmp_path / ".project.json").exists()


def test_runtime_artifacts_do_not_block_first_open(tmp_path):
    from project_guard import build_startup_decision, inspect_project

    (tmp_path / "IEC-site-change-manager.exe").write_text("fake exe", encoding="utf-8")
    (tmp_path / "_internal").mkdir()

    result = inspect_project(tmp_path)
    decision = build_startup_decision(result)

    assert result.state == "first_open"
    assert decision.action == "initialize"


def test_distribution_docs_do_not_block_packaged_first_open(tmp_path):
    from project_guard import build_startup_decision, inspect_project

    (tmp_path / "IEC-site-change-manager.exe").write_text("fake exe", encoding="utf-8")
    (tmp_path / "_internal").mkdir()
    (tmp_path / "README.txt").write_text("release notes", encoding="utf-8")
    (tmp_path / "使用說明.txt").write_text("使用說明", encoding="utf-8")
    (tmp_path / "啟動工務修改單.bat").write_text("@echo off\n", encoding="utf-8")
    (tmp_path / "LibreOffice").mkdir()

    result = inspect_project(tmp_path)
    decision = build_startup_decision(result)

    assert result.state == "first_open"
    assert decision.action == "initialize"


def test_distribution_docs_without_runtime_artifacts_still_block_wrong_folder(tmp_path):
    from project_guard import build_startup_decision, inspect_project

    (tmp_path / "README.txt").write_text("not a package", encoding="utf-8")

    result = inspect_project(tmp_path)
    decision = build_startup_decision(result)

    assert result.has_blocking_issues is True
    assert any(i.code == "possible_wrong_folder" for i in result.issues)
    assert decision.action == "blocked_wrong_folder"


def test_invalid_records_json_blocks_repair(tmp_path):
    from project_guard import build_startup_decision, inspect_project, repair_project

    for dirname in ("attachments", "records", "output", "pdf", "staging", "logs"):
        (tmp_path / dirname).mkdir()
    records_path = tmp_path / "records" / "records.json"
    records_path.write_text("{broken", encoding="utf-8")

    result = inspect_project(tmp_path)
    assert result.has_blocking_issues is True
    assert any(i.code == "records_invalid_json" for i in result.issues)
    assert build_startup_decision(result).action == "blocked"

    repair_project(tmp_path)
    assert records_path.read_text(encoding="utf-8") == "{broken"


def test_snapshot_absolute_path_can_be_repaired(tmp_path):
    from project_guard import build_startup_decision, inspect_project, repair_project

    (tmp_path / "attachments").mkdir()
    (tmp_path / "records").mkdir()
    snapshot_path = tmp_path / "records" / "weld_snapshot.json"
    snapshot_path.write_text(
        json.dumps({
            "attachments_root": str(tmp_path / "attachments"),
            "folders": {},
            "weld_index": {},
        }),
        encoding="utf-8",
    )

    result = inspect_project(tmp_path)
    assert any(i.code == "snapshot_absolute_path" for i in result.issues)
    decision = build_startup_decision(result)
    assert decision.action == "repair"
    assert decision.can_auto_repair is True

    repaired = repair_project(tmp_path)
    assert "weld_snapshot.json 改為相對路徑" in repaired.repaired
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert data["attachments_root"] == "attachments"


def test_project_lock_prevents_second_writer(tmp_path):
    from project_guard import ProjectLock

    lock1 = ProjectLock(tmp_path)
    lock2 = ProjectLock(tmp_path)

    assert lock1.acquire(start_heartbeat=False) is True
    try:
        assert lock2.acquire(start_heartbeat=False) is False
    finally:
        lock1.release()

    assert lock2.acquire(start_heartbeat=False) is True
    lock2.release()


def test_pending_journal_blocks_startup(tmp_path):
    from operation_journal import OperationJournal
    from project_guard import inspect_project

    for dirname in ("attachments", "records", "output", "pdf", "staging", "logs"):
        (tmp_path / dirname).mkdir()
    (tmp_path / "settings.json").write_text('{"paths": {}}', encoding="utf-8")
    OperationJournal(tmp_path, "unfinished").begin()

    result = inspect_project(tmp_path)
    assert result.has_blocking_issues is True
    assert any(i.code == "pending_operation_journal" for i in result.issues)


def test_project_lock_can_take_stale_lock(tmp_path):
    from project_guard import ProjectLock

    lock_path = tmp_path / ".project.lock"
    lock_path.write_text(
        json.dumps({
            "token": "old",
            "pid": 1,
            "user": "old",
            "host": "old",
            "created_at": "2000-01-01T00:00:00",
            "heartbeat_at": "2000-01-01T00:00:00",
        }),
        encoding="utf-8",
    )

    lock = ProjectLock(tmp_path, max_age_seconds=1)
    assert lock.acquire(start_heartbeat=False) is True
    lock.release()


def test_project_lock_can_take_dead_local_pid_even_before_timeout(tmp_path):
    from project_guard import ProjectLock

    lock_path = tmp_path / ".project.lock"
    lock_path.write_text(
        json.dumps({
            "token": "dead-local",
            "pid": 99999999,
            "user": getpass.getuser(),
            "host": socket.gethostname(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "heartbeat_at": datetime.now().isoformat(timespec="seconds"),
        }),
        encoding="utf-8",
    )

    lock = ProjectLock(tmp_path, max_age_seconds=1800)
    assert lock.acquire(start_heartbeat=False) is True
    lock.release()


def test_material_pricebook_missing_items_can_be_repaired(tmp_path):
    from project_guard import inspect_project, repair_project

    (tmp_path / "attachments").mkdir()
    (tmp_path / "records").mkdir()
    pricebook_path = tmp_path / "records" / "material_pricebook.json"
    pricebook_path.write_text('{"meta": {"version": "1.0"}}', encoding="utf-8")

    result = inspect_project(tmp_path)
    assert any(i.code == "material_pricebook_missing_items" for i in result.issues)

    repaired = repair_project(tmp_path)
    assert "修補 records/material_pricebook.json items" in repaired.repaired
    data = json.loads(pricebook_path.read_text(encoding="utf-8"))
    assert data["items"] == []


def test_billing_batches_missing_root_can_be_repaired(tmp_path):
    from project_guard import inspect_project, repair_project

    (tmp_path / "attachments").mkdir()
    (tmp_path / "records").mkdir()
    batches_path = tmp_path / "records" / "billing_batches.json"
    batches_path.write_text('{"meta": {"version": "1.0"}}', encoding="utf-8")

    result = inspect_project(tmp_path)
    assert any(i.code == "billing_batches_missing_root" for i in result.issues)

    repaired = repair_project(tmp_path)
    assert "修補 records/billing_batches.json batches" in repaired.repaired
    data = json.loads(batches_path.read_text(encoding="utf-8"))
    assert data["batches"] == []


def test_duplicate_active_billing_batch_blocks_health(tmp_path):
    from project_guard import inspect_project

    (tmp_path / "attachments").mkdir()
    (tmp_path / "records").mkdir()
    batches_path = tmp_path / "records" / "billing_batches.json"
    batches_path.write_text(
        json.dumps({
            "batches": [
                {"batch_id": "B-001", "status": "請款中", "items": [{"report_id": "R-1"}]},
                {"batch_id": "B-002", "status": "已付款", "items": [{"report_id": "R-1"}]},
            ]
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = inspect_project(tmp_path)

    assert result.has_blocking_issues is True
    assert any(i.code == "billing_batch_duplicate_active_report" for i in result.issues)
