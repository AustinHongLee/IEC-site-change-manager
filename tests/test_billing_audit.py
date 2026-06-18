# -*- coding: utf-8 -*-
"""billing_audit.py 單元測試"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from billing_audit import append_billing_audit, build_billing_change_events


def test_blank_rows_do_not_create_audit_noise():
    events = build_billing_change_events(
        {},
        {"R-1": {
            "status": "",
            "billing_date": "",
            "weld_amount": "",
            "material_amount": "",
            "total": "",
            "remark": "",
        }},
        operation_id="op",
        actor="tester",
        host="host",
        at="2026-06-16T12:00:00",
    )

    assert events == []


def test_default_unbilled_status_does_not_create_audit_noise():
    events = build_billing_change_events(
        {},
        {"R-1": {"status": "未請款"}},
        operation_id="op",
        actor="tester",
        host="host",
        at="2026-06-16T12:00:00",
    )

    assert events == []


def test_builds_old_to_new_change_event():
    events = build_billing_change_events(
        {"R-1": {"status": "未請款", "weld_amount": "100"}},
        {"R-1": {"status": "已請款", "weld_amount": "120", "remark": "送出"}},
        operation_id="op",
        actor="tester",
        host="host",
        at="2026-06-16T12:00:00",
    )

    assert len(events) == 1
    event = events[0]
    assert event["operation_id"] == "op"
    assert event["actor"] == "tester"
    assert event["host"] == "host"
    assert event["report_id"] == "R-1"
    assert event["action"] == "updated"
    assert event["change_types"] == ["amount", "remark", "status"]
    assert event["changes"]["status"] == {"old": "未請款", "new": "已請款"}
    assert event["changes"]["weld_amount"] == {"old": "100", "new": "120"}
    assert event["changes"]["remark"] == {"old": "", "new": "送出"}


def test_clearing_legacy_manual_total_is_audited():
    events = build_billing_change_events(
        {"R-1": {"weld_amount": "100", "material_amount": "50", "total": "999"}},
        {"R-1": {"weld_amount": "100", "material_amount": "50", "total": ""}},
        operation_id="op",
        actor="tester",
        host="host",
        at="2026-06-16T12:00:00",
    )

    assert len(events) == 1
    assert events[0]["change_types"] == ["amount"]
    assert events[0]["changes"]["total"] == {"old": "999", "new": ""}


def test_append_billing_audit_writes_jsonl(tmp_path):
    events = build_billing_change_events(
        {},
        {"R-1": {"status": "請款中", "billing_date": "20260616"}},
        operation_id="op",
        actor="tester",
        host="host",
        at="2026-06-16T12:00:00",
    )

    path, count = append_billing_audit(tmp_path, events)

    assert count == 1
    assert path == tmp_path / "records" / "billing_audit.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["changes"]["status"] == {"old": "", "new": "請款中"}
