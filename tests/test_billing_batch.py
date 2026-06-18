# -*- coding: utf-8 -*-
"""billing_batch.py 單元測試"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from billing_batch import (
    BillingBatchError,
    active_batch_index,
    create_billing_batch,
    load_billing_batches,
    save_billing_batches,
    update_billing_batch_status,
    validate_billing_batches,
)


def test_create_billing_batch_writes_minimal_batch(tmp_path):
    path = tmp_path / "billing_batches.json"

    batch = create_billing_batch(
        ["R-1", "R-2", "R-1"],
        path=path,
        batch_id="B-001",
        client="業主A",
        period="2026-06",
        actor="tester",
        at="2026-06-16T12:00:00",
    )

    data = load_billing_batches(path)

    assert batch["batch_id"] == "B-001"
    assert batch["status"] == "草稿"
    assert [item["report_id"] for item in batch["items"]] == ["R-1", "R-2"]
    assert data["meta"]["version"] == "1.0"
    assert data["meta"]["currency"] == "TWD"
    assert data["batches"][0]["client"] == "業主A"
    assert json.loads(path.read_text(encoding="utf-8"))["batches"][0]["period"] == "2026-06"


def test_duplicate_report_in_active_batches_is_rejected(tmp_path):
    path = tmp_path / "billing_batches.json"
    create_billing_batch(["R-1"], path=path, batch_id="B-001")

    with pytest.raises(BillingBatchError) as excinfo:
        create_billing_batch(["R-1"], path=path, batch_id="B-002")

    assert excinfo.value.issues[0].code == "duplicate_active_report"
    assert excinfo.value.issues[0].report_id == "R-1"


def test_closed_batch_does_not_block_new_active_batch(tmp_path):
    path = tmp_path / "billing_batches.json"
    save_billing_batches({
        "batches": [{
            "batch_id": "B-OLD",
            "status": "已結案",
            "items": [{"report_id": "R-1"}],
        }]
    }, path)

    create_billing_batch(["R-1"], path=path, batch_id="B-NEW")

    data = load_billing_batches(path)
    assert [batch["batch_id"] for batch in data["batches"]] == ["B-OLD", "B-NEW"]
    assert active_batch_index(data) == {"R-1": "B-NEW"}


def test_validate_billing_batches_reports_duplicate_active_refs():
    issues = validate_billing_batches({
        "batches": [
            {"batch_id": "B-001", "status": "請款中", "items": [{"report_id": "R-1"}]},
            {"batch_id": "B-002", "status": "已付款", "items": [{"report_id": "R-1"}]},
        ]
    })

    assert len(issues) == 1
    assert issues[0].code == "duplicate_active_report"
    assert "不可同時加入" in issues[0].message


def test_update_batch_status_rejects_jump_transition():
    data = {
        "batches": [{
            "batch_id": "B-001",
            "status": "草稿",
            "items": [{"report_id": "R-1"}],
        }]
    }

    with pytest.raises(BillingBatchError) as excinfo:
        update_billing_batch_status(data, "B-001", "已付款")

    assert excinfo.value.issues[0].code == "invalid_batch_transition"
    assert "不可由「草稿」直接改為「已付款」" in excinfo.value.issues[0].message


def test_update_batch_status_allows_normal_progression():
    data = {
        "batches": [{
            "batch_id": "B-001",
            "status": "草稿",
            "items": [{"report_id": "R-1"}],
        }]
    }

    updated = update_billing_batch_status(
        data,
        "B-001",
        "請款中",
        actor="tester",
        at="2026-06-16T12:30:00",
    )

    assert updated["batches"][0]["status"] == "請款中"
    assert updated["batches"][0]["updated_by"] == "tester"
    assert updated["batches"][0]["updated_at"] == "2026-06-16T12:30:00"


def test_empty_batch_is_rejected():
    with pytest.raises(BillingBatchError) as excinfo:
        create_billing_batch([], path="unused.json", batch_id="B-EMPTY")

    assert excinfo.value.issues[0].code == "empty_batch"
