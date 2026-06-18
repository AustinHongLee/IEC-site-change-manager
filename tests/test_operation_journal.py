# -*- coding: utf-8 -*-
"""
test_operation_journal.py - 多檔操作 journal 測試
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))


def test_journal_complete_removes_file(tmp_path):
    from operation_journal import OperationJournal, list_pending_journals

    journal = OperationJournal(tmp_path, "test_operation").begin()
    path = journal.path
    assert path.exists()
    journal.step("rename", source="a", target="b")
    journal.complete()

    assert not path.exists()
    assert list_pending_journals(tmp_path) == []


def test_journal_fail_keeps_file(tmp_path):
    from operation_journal import OperationJournal, list_pending_journals

    journal = OperationJournal(tmp_path, "test_operation").begin()
    path = journal.path
    journal.step("write_json", path="records.json")
    journal.fail("boom")

    assert path.exists()
    assert list_pending_journals(tmp_path) == [str(path)]
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["error"] == "boom"


def test_context_manager_records_exception(tmp_path):
    from operation_journal import OperationJournal, list_pending_journals

    try:
        with OperationJournal(tmp_path, "ctx_operation") as journal:
            path = journal.path
            raise RuntimeError("bad")
    except RuntimeError:
        pass

    assert list_pending_journals(tmp_path) == [str(path)]
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
