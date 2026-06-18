# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from canonical_report import collect_canonical_report_set, list_field_paths


def test_collects_unproduced_attachment_folder_as_canonical_report(tmp_path):
    folder = tmp_path / "attachments" / "20260112" / "0547_AG"
    folder.mkdir(parents=True)
    (folder / "GroupWeld.txt").write_text("1A2\n2R1\n", encoding="utf-8")
    (folder / "note.txt").write_text("現場加長修改", encoding="utf-8")
    (folder / "materials.txt").write_text(
        "Elbow (彎頭),2\",SCH 40,SS,1 個,現場用料\n",
        encoding="utf-8",
    )
    (folder / "before_1.jpg").write_bytes(b"fake")
    (folder / "after_1.jpg").write_bytes(b"fake")

    result = collect_canonical_report_set(
        project_root=tmp_path,
        attachments_root=tmp_path / "attachments",
        store={"records": [], "details": [], "materials": []},
    )

    assert result["schema_version"] == "report_set.v1"
    assert result["aggregates"]["report_count"] == 1
    report = result["reports"][0]
    assert report["report"]["status"] == "unproduced"
    assert report["report"]["series"] == "0547"
    assert report["welds"]["count"] == 2
    assert report["materials"]["count"] == 1
    assert report["photos"]["has_before"] is True
    assert report["photos"]["has_after"] is True
    assert report["completeness"]["level"] == "complete"


def test_report_set_issues_include_record_locator_fields(tmp_path):
    folder = tmp_path / "attachments" / "20260112" / "0547_AG"
    folder.mkdir(parents=True)
    (folder / "GroupWeld.txt").write_text("1A2\n", encoding="utf-8")
    (folder / "note.txt").write_text("", encoding="utf-8")

    result = collect_canonical_report_set(
        project_root=tmp_path,
        attachments_root=tmp_path / "attachments",
        store={"records": [], "details": [], "materials": []},
    )

    issue = next(item for item in result["issues"] if item["code"] == "note")
    assert issue["report"] == "0547_AG"
    assert issue["report_id"] == ""
    assert issue["date"] == "20260112"
    assert issue["folder"] == "0547_AG"


def test_collects_records_details_and_materials_into_canonical_shape(tmp_path):
    folder = tmp_path / "attachments" / "20260616" / "001_1r2"
    folder.mkdir(parents=True)
    (folder / "note.txt").write_text("已產出修改", encoding="utf-8")
    (folder / "before.jpg").write_bytes(b"fake")
    (folder / "after.jpg").write_bytes(b"fake")
    store = {
        "records": [{
            "日期": "20260616",
            "報告編號": "20260616-01",
            "Series NO": "0001",
            "DWG NO": "DWG-1",
            "LINE NUMBER": "L-1",
            "變更類型": "裁切重焊",
            "說明": "已產出修改",
            "資料夾名": "001_1r2",
            "內容指紋": "abc",
            "需重產": "1",
        }],
        "details": [{
            "紀錄編號": "20260616-01",
            "焊口編號": "1r",
            "焊口尺寸": "2",
            "材質": "SS",
            "厚度": "SCH 40",
        }],
        "materials": [{
            "報告編號": "20260616-01",
            "零件類型": "Pipe (管)",
            "尺寸": "2\"",
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "數量": "3",
            "單位": "M",
        }],
    }

    result = collect_canonical_report_set(
        project_root=tmp_path,
        attachments_root=tmp_path / "attachments",
        store=store,
    )

    report = result["reports"][0]
    assert report["report"]["status"] == "needs_rebuild"
    assert report["report"]["report_id"] == "20260616-01"
    assert report["report"]["fingerprint"] == "abc"
    assert report["welds"]["rows"][0]["code"] == "1r"
    assert report["welds"]["total_size"] == 2.0
    assert report["materials"]["rows"][0]["component"] == "Pipe (管)"
    assert result["aggregates"]["status_counts"]["needs_rebuild"] == 1
    assert result["aggregates"]["weld_count"] == 1
    assert result["aggregates"]["material_row_count"] == 1


def test_field_path_catalog_contains_template_contract_paths():
    fields = list_field_paths()

    assert "report.report_id" in fields
    assert "welds.rows[*].code" in fields
    assert "materials.rows[*].component" in fields
    assert "photos.before[*]" in fields
    assert "photos.before[*].path" in fields
    assert "photos.before[0..n]" not in fields
