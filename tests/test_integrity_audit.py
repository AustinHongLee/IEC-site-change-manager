# -*- coding: utf-8 -*-
"""
test_integrity_audit.py - 專案資料一致性稽核測試
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_clean_project(tmp_path):
    for dirname in ("attachments", "records", "output", "pdf", "staging", "logs"):
        (tmp_path / dirname).mkdir()
    folder = tmp_path / "attachments" / "20260101" / "001_1r1"
    folder.mkdir(parents=True)
    (folder / "before.jpg").write_bytes(b"jpg")
    (folder / "after.jpg").write_bytes(b"jpg")
    (tmp_path / "pdf" / "20260101-01.pdf").write_bytes(b"%PDF")

    _write_json(tmp_path / "records" / "records.json", {
        "records": [{
            "日期": "20260101",
            "報告編號": "20260101-01",
            "資料夾名": "001_1r1",
            "before.jpg": "有",
            "after.jpg": "有",
        }],
        "details": [{"紀錄編號": "20260101-01", "焊口編號": "1r1"}],
        "materials": [],
        "meta": {"version": "2.0"},
    })
    _write_json(tmp_path / "records" / "billing.json", {
        "billing": {"20260101-01": {"status": "未請款"}},
        "meta": {"version": "1.0"},
    })
    _write_json(tmp_path / "records" / "billing_batches.json", {
        "batches": [],
        "meta": {"version": "1.0"},
    })
    _write_json(tmp_path / "records" / "dwg_map.json", {
        "mapping": {},
        "count": 0,
    })
    _write_json(tmp_path / "records" / "weld_snapshot.json", {
        "attachments_root": "attachments",
        "folders": {"20260101/001_1r1": {}},
        "weld_index": {},
    })


def test_clean_project_has_no_issues(tmp_path):
    from integrity_audit import audit_integrity

    _make_clean_project(tmp_path)
    report = audit_integrity(tmp_path)

    assert report.total_issues == 0
    assert report.has_errors is False
    assert report.counts["records"] == 1
    assert report.counts["attachment_folders"] == 1


def test_attachment_without_record_is_warning(tmp_path):
    from integrity_audit import audit_integrity

    _make_clean_project(tmp_path)
    extra = tmp_path / "attachments" / "20260102" / "002_1r1"
    extra.mkdir(parents=True)

    report = audit_integrity(tmp_path)

    assert report.has_errors is False
    assert any(i.code == "attachments_without_records" for i in report.issues)


def test_missing_attachment_for_record_is_error(tmp_path):
    from integrity_audit import audit_integrity

    _make_clean_project(tmp_path)
    folder = tmp_path / "attachments" / "20260101" / "001_1r1"
    for child in folder.iterdir():
        child.unlink()
    folder.rmdir()

    report = audit_integrity(tmp_path)

    assert report.has_errors is True
    assert any(i.code == "records_missing_attachments" for i in report.issues)


def test_billing_reference_without_record_is_error(tmp_path):
    from integrity_audit import audit_integrity

    _make_clean_project(tmp_path)
    _write_json(tmp_path / "records" / "billing.json", {
        "billing": {
            "20260101-01": {"status": "未請款"},
            "missing-record": {"status": "已請款"},
        },
        "meta": {"version": "1.0"},
    })

    report = audit_integrity(tmp_path)

    assert report.has_errors is True
    assert any(i.code == "billing_refs_missing_records" for i in report.issues)


def test_duplicate_active_billing_batch_is_error(tmp_path):
    from integrity_audit import audit_integrity

    _make_clean_project(tmp_path)
    _write_json(tmp_path / "records" / "billing_batches.json", {
        "batches": [
            {"batch_id": "B-001", "status": "請款中", "items": [{"report_id": "20260101-01"}]},
            {"batch_id": "B-002", "status": "已付款", "items": [{"report_id": "20260101-01"}]},
        ],
        "meta": {"version": "1.0"},
    })

    report = audit_integrity(tmp_path)

    assert report.has_errors is True
    assert any(i.code == "billing_batch_duplicate_active_report" for i in report.issues)
    assert report.counts["billing_batch_refs"] == 1


def test_duplicate_report_id_is_error(tmp_path):
    from integrity_audit import audit_integrity

    _make_clean_project(tmp_path)
    store = json.loads((tmp_path / "records" / "records.json").read_text(encoding="utf-8"))
    store["records"].append({
        "日期": "20260103",
        "報告編號": "20260101-01",
        "資料夾名": "003_1r1",
        "before.jpg": "無",
        "after.jpg": "無",
    })
    (tmp_path / "attachments" / "20260103" / "003_1r1").mkdir(parents=True)
    _write_json(tmp_path / "records" / "records.json", store)

    report = audit_integrity(tmp_path)

    assert report.has_errors is True
    assert any(i.code == "duplicate_report_ids" for i in report.issues)
