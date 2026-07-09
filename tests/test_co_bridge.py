import os
import sys
import base64
import json
from datetime import datetime

import pytest
from openpyxl import Workbook

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from change_order import ChangeOrder, Status  # noqa: E402
from change_order_builder import ChangeOrderBuilder  # noqa: E402
from co_bridge import ChangeOrderBridge  # noqa: E402
from weld_control import WeldControlManager  # noqa: E402
from weld_lookup import WeldLookup  # noqa: E402


def _fixed_clock():
    return datetime(2026, 6, 24, 9, 0, 0)


def _write_fixture(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "焊口編號明細"
    ws.append(["流水號", "銲口編號", "尺寸", "厚度", "材質", "銲接型式", "屬性.1", "圖號"])
    ws.append([100, "5", '2"', "SCH40", "SUS304", "BW", "焊口", "DWG-100"])
    ws.append([100, "5a", '2"', "SCH40", "SUS304", "BW", "焊口", "DWG-100"])
    ws.append([100, "8V", '3"', "SCH10", "SUS316", "RF", "VALVE安裝", "DWG-100"])
    wb.save(path)
    wb.close()


def _write_pdf(path, pages=1):
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=200)
    with open(path, "wb") as f:
        writer.write(f)


def _tiny_png_data_url():
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (12, 8), (255, 255, 255)).save(buf, format="PNG")
    raw = buf.getvalue()
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _bridge(tmp_path):
    wb = tmp_path / "weld_control.xlsx"
    _write_fixture(wb)
    manager = WeldControlManager({
        "file_path": str(wb), "sheet_name": "焊口編號明細",
        "col_serial": "流水號", "col_weld_no": "焊口編號",
    })
    builder = ChangeOrderBuilder(lookup=WeldLookup(manager=manager), clock=_fixed_clock)
    return ChangeOrderBridge(builder=builder, attachments_root=tmp_path / "records")


def _bridge_with_records(tmp_path):
    bridge = _bridge(tmp_path)
    bridge.records_dir = tmp_path / "records_data"
    bridge.records_dir.mkdir()
    return bridge


def test_envelope_shape(tmp_path):
    res = _bridge(tmp_path).info()
    assert set(res) >= {"ok", "data", "error"}
    assert res["ok"] is True and res["data"]["api_version"]


def test_existing_welds_filters_install_rows(tmp_path):
    res = _bridge(tmp_path).existing_welds("0100")
    assert res["ok"] is True
    assert res["data"]["source"]["ok"] is True
    assert res["data"]["source"]["sheet"] == "焊口編號明細"
    assert res["data"]["source"]["count"] == 3
    assert res["data"]["source"]["series_count"] == 2
    nos = [w["weld_no"] for w in res["data"]["welds"]]
    assert "5" in nos and "8V" not in nos          # 安裝列被濾
    row5 = next(w for w in res["data"]["welds"] if w["weld_no"] == "5")
    assert row5["material"] == "SUS304" and row5["size"] == '2"'


def test_existing_welds_reports_source_failure_when_sheet_unreadable(tmp_path):
    wb = tmp_path / "weld_control.xlsx"
    _write_fixture(wb)
    manager = WeldControlManager({
        "file_path": str(wb), "sheet_name": "不存在的工作表",
        "col_serial": "完全不存在的流水欄", "col_weld_no": "完全不存在的焊口欄",
    })
    builder = ChangeOrderBuilder(lookup=WeldLookup(manager=manager), clock=_fixed_clock)
    res = ChangeOrderBridge(builder=builder, attachments_root=tmp_path / "records").existing_welds("0100")

    assert res["ok"] is True
    assert res["data"]["welds"] == []
    assert res["data"]["source"]["ok"] is False
    assert "載入失敗" in res["data"]["source"]["message"]


def test_history_reads_records_for_series_newest_first_and_skips_bad_files(tmp_path):
    bridge = _bridge(tmp_path)
    root = tmp_path / "records"
    root.mkdir()

    def write_record(folder_name, *, date, welds, reason):
        folder = root / folder_name
        folder.mkdir()
        payload = {
            "id": folder_name,
            "series": "100",
            "date": date,
            "reason": reason,
            "welds": [{"code": code} for code in welds],
        }
        (folder / "change_order.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return folder

    newer = write_record("100_20260625_01", date="20260625", welds=["5b", "1001"], reason="後做")
    older = write_record("100_20260624_01", date="20260624", welds=["3a"], reason="先做")
    write_record("10_20260625_01", date="20260625", welds=["1a"], reason="不同流水號")

    bad = root / "100_broken_01"
    bad.mkdir()
    (bad / "change_order.json").write_text("{not json", encoding="utf-8")

    res = bridge.history("0100")
    assert res["ok"] is True
    rows = res["data"]
    assert [row["id"] for row in rows] == ["100_20260625_01", "100_20260624_01"]
    assert rows[0]["welds"] == ["5b", "1001"]
    assert rows[0]["reason"] == "後做"
    assert rows[0]["folder"] == str(newer)
    assert rows[1]["folder"] == str(older)


def test_build_returns_codes_status_issues(tmp_path):
    payload = {
        "series": "0100", "date": "20260624", "reason": "現場干涉",
        "welds": [
            {"kind": "existing", "base": "5", "op": "重焊"},
            {"kind": "new", "op": "新焊", "spec": {"size": '1"', "material": "SUS304"}},
        ],
    }
    res = _bridge(tmp_path).build(payload)
    assert res["ok"] is True
    co = res["data"]["co"]
    assert co["series"] == "100"                    # 邊界正規化
    assert [w["code"] for w in co["welds"]] == ["5b", "1001"]   # 既有重焊→5b、新→1001
    assert [w["op"] for w in co["welds"]] == ["重焊", "新焊"]
    assert res["data"]["status"] == "待補"          # 還沒照片/pdf
    codes = {i["code"] for i in res["data"]["issues"]}
    assert "missing_before_photo" in codes


def test_build_reserves_historical_weld_codes_for_same_series(tmp_path):
    bridge = _bridge(tmp_path)
    root = tmp_path / "records"
    history = root / "100_20260623_01"
    history.mkdir(parents=True)
    (history / "change_order.json").write_text(json.dumps({
        "id": "100_20260623_01",
        "series": "100",
        "date": "20260623",
        "welds": [{"code": "5b"}, {"code": "1001"}],
    }, ensure_ascii=False), encoding="utf-8")
    other = root / "1000_20260623_01"
    other.mkdir()
    (other / "change_order.json").write_text(json.dumps({
        "id": "1000_20260623_01",
        "series": "1000",
        "welds": [{"code": "5z"}, {"code": "1999"}],
    }, ensure_ascii=False), encoding="utf-8")

    res = bridge.build({
        "series": "0100",
        "date": "20260624",
        "welds": [
            {"kind": "existing", "base": "5", "op": "重焊"},
            {"kind": "new", "op": "新焊", "spec": {"size": '1"', "material": "SUS304"}},
        ],
    })

    assert res["ok"] is True
    assert [w["code"] for w in res["data"]["co"]["welds"]] == ["5c", "1002"]


def test_build_excludes_current_record_from_historical_weld_reservations(tmp_path):
    bridge = _bridge(tmp_path)
    root = tmp_path / "records"
    current = root / "100_20260624_01"
    current.mkdir(parents=True)
    (current / "change_order.json").write_text(json.dumps({
        "id": "100_20260624_01",
        "series": "100",
        "date": "20260624",
        "welds": [{"code": "5b"}, {"code": "1001"}],
    }, ensure_ascii=False), encoding="utf-8")

    res = bridge.build({
        "current_id": "100_20260624_01",
        "series": "0100",
        "date": "20260624",
        "welds": [
            {"kind": "existing", "base": "5", "op": "重焊"},
            {"kind": "new", "op": "新焊", "spec": {"size": '1"', "material": "SUS304"}},
        ],
    })

    assert res["ok"] is True
    assert [w["code"] for w in res["data"]["co"]["welds"]] == ["5b", "1001"]


def test_export_blocks_when_not_complete_then_succeeds(tmp_path):
    b = _bridge(tmp_path)
    base = {
        "series": "100", "date": "20260624",
        "welds": [{"kind": "existing", "base": "5", "op": "重焊"}],
    }
    # finalize 在未完整時被擋
    blocked = b.export(base, finalize=True)
    assert blocked["ok"] is True and blocked["data"]["exported"] is False
    assert blocked["data"]["reason"] == "not_complete"

    # 補齊照片/pdf（指向 temp 假檔）→ 出單成功、檔案複製、相對名
    before = tmp_path / "b.jpg"; before.write_bytes(b"b")
    after = tmp_path / "a.jpg"; after.write_bytes(b"a")
    pdf = tmp_path / "d.pdf"; pdf.write_bytes(b"%PDF")
    full = dict(base, photos=[{"role": "before", "file": str(before)},
                              {"role": "after", "file": str(after)}],
               drawing_pdf=str(pdf))
    ok = b.export(full, finalize=True)
    assert ok["ok"] is True and ok["data"]["exported"] is True
    loaded = ChangeOrder.load_json(ok["data"]["record"])
    assert loaded.id == "100_20260624_01"
    assert [p.file for p in loaded.photos] == ["before_1.jpg", "after_1.jpg"]
    assert loaded.drawing_pdf.file == "drawing.pdf"


def test_pick_file_without_injection_returns_error_envelope(tmp_path):
    res = _bridge(tmp_path).pick_file("pdf")
    assert res["ok"] is False and "未注入" in res["error"]   # 不崩，給明確錯


def test_auto_drawing_pdf_finds_series_pdf_and_avoids_prefix_bleed(tmp_path):
    prefab = tmp_path / "prefab_pdf"
    nested = prefab / "nested"
    nested.mkdir(parents=True)
    (prefab / "1000.CA-wrong.pdf").write_bytes(b"%PDF-1000")
    (nested / "0100.CA-nested.pdf").write_bytes(b"%PDF-0100")
    expected = prefab / "100.CA-2007-100-AA1B-NA.pdf"
    expected.write_bytes(b"%PDF-100")

    res = _bridge(tmp_path).auto_drawing_pdf("0100", str(prefab))

    assert res["ok"] is True
    assert res["data"]["found"] is True
    assert res["data"]["path"] == str(expected)
    assert res["data"]["name"] == expected.name

    miss = _bridge(tmp_path).auto_drawing_pdf("10", str(prefab))
    assert miss["ok"] is True
    assert miss["data"]["found"] is False
    assert miss["data"]["reason"] == "not_found"


def test_auto_drawing_pdf_reports_missing_source_dir(tmp_path):
    res = _bridge(tmp_path).auto_drawing_pdf("100", str(tmp_path / "missing"))

    assert res["ok"] is True
    assert res["data"]["found"] is False
    assert res["data"]["reason"] == "missing_dir"


def test_auto_drawing_pdf_requires_series(tmp_path):
    res = _bridge(tmp_path).auto_drawing_pdf("", str(tmp_path))

    assert res["ok"] is True
    assert res["data"]["found"] is False
    assert res["data"]["reason"] == "missing_series"


def test_list_staging_returns_image_files_only(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    photo = staging / "photo.jpg"
    diagram = staging / "diagram.PNG"
    photo.write_bytes(b"jpg")
    diagram.write_bytes(b"png")
    (staging / "notes.txt").write_text("skip", encoding="utf-8")
    (staging / "nested").mkdir()

    res = _bridge(tmp_path).list_staging()
    assert res["ok"] is True
    rows = res["data"]
    assert {row["name"] for row in rows} == {"photo.jpg", "diagram.PNG"}
    assert {row["path"] for row in rows} == {str(photo), str(diagram)}


def test_project_parts_returns_registered_material_rows(tmp_path):
    bridge = _bridge_with_records(tmp_path)
    (bridge.records_dir / "material_pricebook.json").write_text(json.dumps({"items": [
        {"id": "0001", "零件類型": "無縫鋼管", "尺寸": "DN15", "SCH": "SCH80",
         "材質": "A106 GR.B", "類別": "配管", "單位": "米", "來源": "管制"},
        {"id": "0002", "零件類型": "90°彎頭", "尺寸": "DN15", "SCH": "SCH80",
         "材質": "A105", "類別": "配管", "單位": "個", "來源": "管制"},
    ]}, ensure_ascii=False), encoding="utf-8")
    (bridge.records_dir / "project_parts.json").write_text(
        json.dumps({"registered": ["0002", "missing"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    res = bridge.project_parts()

    assert res["ok"] is True
    data = res["data"]
    assert data["registered"] == ["0002", "missing"]
    assert data["count"] == 1
    assert data["items"] == [{
        "id": "0002",
        "part": "90°彎頭",
        "size": "DN15",
        "sch": "SCH80",
        "mat": "A105",
        "cat": "配管",
        "unit": "個",
        "src": "管制",
        "remark": "",
    }]


def test_build_preserves_material_component_id(tmp_path):
    payload = {
        "series": "100",
        "date": "20260701",
        "materials": [{
            "component_id": "0002",
            "component": "90°彎頭",
            "size": "DN15",
            "schedule": "SCH80",
            "material": "A105",
            "qty": "2",
            "unit": "個",
            "remark": "",
        }],
    }

    res = _bridge(tmp_path).build(payload)

    assert res["ok"] is True
    assert res["data"]["co"]["materials"][0]["component_id"] == "0002"


def test_save_annotated_writes_png_and_returns_path(tmp_path):
    raw = b"\x89PNG\r\n\x1a\nannotated"
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

    res = _bridge(tmp_path).save_annotated(data_url, "before photo.jpg")

    assert res["ok"] is True
    saved = res["data"]["path"]
    assert saved.endswith(".png")
    assert os.path.basename(saved).startswith("before_photo_")
    assert os.path.dirname(saved).endswith("_annotated")
    assert open(saved, "rb").read() == raw


def test_image_data_url_reads_absolute_image_path(tmp_path):
    raw = b"fake-jpeg-bytes"
    photo = tmp_path / "photo name.jpg"
    photo.write_bytes(raw)

    res = _bridge(tmp_path).image_data_url(str(photo))

    assert res["ok"] is True
    data = res["data"]
    assert data["name"] == "photo name.jpg"
    assert data["path"] == str(photo.resolve())
    assert data["url"].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(data["url"].split(",", 1)[1]) == raw


def test_image_data_url_accepts_file_url(tmp_path):
    raw = b"png-bytes"
    photo = tmp_path / "space photo.png"
    photo.write_bytes(raw)

    res = _bridge(tmp_path).image_data_url(photo.as_uri())

    assert res["ok"] is True
    data = res["data"]
    assert data["name"] == "space photo.png"
    assert data["url"].startswith("data:image/png;base64,")
    assert base64.b64decode(data["url"].split(",", 1)[1]) == raw


def test_image_data_url_resolves_relative_exported_photo(tmp_path):
    raw = b"webp-bytes"
    photo = tmp_path / "records" / "100_20260624_01" / "after_1.webp"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(raw)

    res = _bridge(tmp_path).image_data_url("100_20260624_01/after_1.webp")

    assert res["ok"] is True
    data = res["data"]
    assert data["path"] == str(photo.resolve())
    assert data["url"].startswith("data:image/webp;base64,")
    assert base64.b64decode(data["url"].split(",", 1)[1]) == raw


def test_pdf_page_data_url_renders_first_page(tmp_path):
    pytest.importorskip("fitz")
    pdf = tmp_path / "drawing.pdf"
    _write_pdf(pdf, pages=2)

    res = _bridge(tmp_path).pdf_page_data_url(str(pdf), 0)

    assert res["ok"] is True
    data = res["data"]
    assert data["name"] == "drawing.pdf"
    assert data["page_index"] == 0
    assert data["page_count"] == 2
    assert data["url"].startswith("data:image/png;base64,")
    assert base64.b64decode(data["url"].split(",", 1)[1]).startswith(b"\x89PNG")


def test_save_pdf_annotation_returns_readable_pdf_and_keeps_source(tmp_path):
    pytest.importorskip("fitz")
    from pypdf import PdfReader

    pdf = tmp_path / "drawing.pdf"
    _write_pdf(pdf, pages=2)

    res = _bridge(tmp_path).save_pdf_annotation(_tiny_png_data_url(), str(pdf), 0)

    assert res["ok"] is True
    saved = res["data"]["path"]
    assert saved.endswith(".pdf")
    assert os.path.dirname(saved).endswith("_annotated")
    assert os.path.exists(pdf)
    assert len(PdfReader(saved).pages) == 2
