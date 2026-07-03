# -*- coding: utf-8 -*-

import os
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfWriter


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from owner_data_report import build_owner_data_report_package


def _write_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as f:
        writer.write(f)


def _report_set(tmp_path: Path) -> dict:
    source = tmp_path / "source" / "20260702" / "720_3r2_3a2"
    source.mkdir(parents=True)
    before = source / "before_1.jpg"
    after = source / "after_1.jpg"
    pdf = source / "720.CA-2007-100-AA1B-NA-1.pdf"
    Image.new("RGB", (80, 160), (180, 40, 40)).save(before)
    Image.new("RGB", (180, 80), (40, 90, 180)).save(after)
    _write_pdf(pdf)
    return {
        "schema_version": "report_set.v1",
        "project": {
            "root": str(tmp_path),
            "attachments_root": str(tmp_path / "source"),
            "collected_at": "2026-07-02T10:00:00",
        },
        "reports": [{
            "report": {
                "report_id": "R-720",
                "date": "2026-07-02",
                "date_raw": "20260702",
                "series": "0720",
                "dwg_no": "CA-2007-100-AA1B-NA",
                "line_number": "L-100",
                "folder": "720_3r2_3a2",
                "folder_path": str(source),
                "status": "produced",
                "change_type": "現場修改",
                "description": "因現場管線干涉，切除原焊口並新增焊口。",
            },
            "welds": {
                "summary": "3r、3a（共2口）",
                "count": 2,
                "rows": [
                    {"code": "3r", "size": 3, "material": "C.S", "thickness": "S-40", "mark": "r"},
                    {"code": "3a", "size": 3, "material": "C.S", "thickness": "S-40", "mark": "a"},
                ],
            },
            "materials": {
                "summary": "管材×1",
                "count": 1,
                "rows": [{
                    "component": "管材",
                    "size": "DN80",
                    "sch": "SCH40",
                    "material": "C.S",
                    "qty": 1,
                    "unit": "米",
                    "remark": "",
                }],
            },
            "photos": {
                "before": [{"name": before.name, "path": str(before), "w": 80, "h": 160}],
                "after": [{"name": after.name, "path": str(after), "w": 180, "h": 80}],
            },
            "attachment_pdf": {"path": str(pdf), "name": pdf.name, "exists": True, "pages": 1},
            "completeness": {"level": "complete", "missing": []},
        }],
        "aggregates": {
            "report_count": 1,
            "weld_count": 2,
            "material_row_count": 1,
            "photo_count": 2,
            "before_photo_count": 1,
            "after_photo_count": 1,
        },
        "issues": [],
    }


def test_owner_data_report_package_copies_assets_and_builds_index(tmp_path):
    output = tmp_path / "out"

    result = build_owner_data_report_package(output, _report_set(tmp_path))

    package = Path(result["package_root"])
    index = Path(result["index_xlsx"])
    report_dir = package / "R-720"
    assert package.exists()
    assert index.exists()
    assert (report_dir / "before").is_dir()
    assert (report_dir / "after").is_dir()
    assert (report_dir / "pdf").is_dir()
    assert list((report_dir / "before").glob("*.jpg"))
    assert list((report_dir / "after").glob("*.jpg"))
    assert list((report_dir / "pdf").glob("*.pdf"))

    wb = load_workbook(index, data_only=False)
    try:
        assert wb.sheetnames == ["封面", "資料索引", "照片明細", "焊口統計", "用料統計"]
        assert wb["封面"]["A1"].value == "現場修改資料包索引"
        assert wb["資料索引"]["A3"].value == "R-720"
        assert wb["資料索引"]["D3"].value == "CA-2007-100-AA1B-NA"
        assert not wb["資料索引"]["I3"].value
        assert wb["資料索引"]["I3"].hyperlink is None
        assert not wb["資料索引"]["J3"].value
        assert wb["資料索引"]["J3"].hyperlink is None
        assert not wb["資料索引"]["K3"].value
        assert wb["資料索引"]["K3"].hyperlink is None
        assert wb["資料索引"]["F3"].hyperlink.target == "R-720"
        assert wb["資料索引"]["L3"].hyperlink.target == "R-720/before"
        assert wb["資料索引"]["M3"].hyperlink.target == "R-720/after"
        assert wb["資料索引"]["N3"].hyperlink.target.endswith(".pdf")
        assert wb["資料索引"]["G3"].value == "3r\n3a\n（共2口）"
        assert wb["資料索引"]["H3"].value == "管材×1"
        assert wb["資料索引"]["G3"].alignment.vertical == "top"
        assert wb["資料索引"]["G3"].alignment.wrap_text is True
        assert wb["資料索引"]["F3"].alignment.horizontal == "center"
        assert wb["資料索引"]["L3"].alignment.horizontal == "center"
        assert wb["資料索引"]["M3"].alignment.horizontal == "center"
        assert wb["資料索引"]["N3"].alignment.horizontal == "center"
        assert not wb["照片明細"]["D3"].value
        assert wb["照片明細"]["D3"].hyperlink is None
        assert not wb["照片明細"]["E3"].value
        assert wb["照片明細"]["E3"].hyperlink is None
        assert wb["照片明細"]["F3"].alignment.horizontal == "center"
        assert wb["資料索引"].row_dimensions[3].height >= 118
    finally:
        wb.close()

    moved_package = tmp_path / "moved_owner_data_report"
    shutil.copytree(package, moved_package)
    moved_index = moved_package / "owner_data_index.xlsx"
    moved_wb = load_workbook(moved_index, data_only=False)
    try:
        ws = moved_wb["資料索引"]
        for coordinate in ("F3", "L3", "M3", "N3"):
            target = ws[coordinate].hyperlink.target
            assert not os.path.isabs(target)
            assert (moved_package / target).exists()
    finally:
        moved_wb.close()

    with ZipFile(index) as archive:
        media = [name for name in archive.namelist() if name.startswith("xl/media/")]
    assert len(media) >= 3


def test_owner_data_report_displays_clean_report_labels_for_folder_ids(tmp_path):
    output = tmp_path / "out"
    report_set = _report_set(tmp_path)
    report_set["reports"][0]["report"]["report_id"] = ""
    report_set["reports"][0]["report"]["folder"] = "107_20260701_01"
    report_set["reports"][0]["report"]["series"] = "0107"
    report_set["reports"][0]["report"]["date_raw"] = "20260701"

    result = build_owner_data_report_package(output, report_set)

    package = Path(result["package_root"])
    index = Path(result["index_xlsx"])
    report_dir = package / "CO-107-20260701-01"
    assert report_dir.is_dir()

    wb = load_workbook(index, data_only=False)
    try:
        ws = wb["資料索引"]
        assert ws["A3"].value == "CO-107-20260701-01"
        assert ws["F3"].value == "CO-107-20260701-01"
        assert ws["F3"].hyperlink.target == "CO-107-20260701-01"
    finally:
        wb.close()
