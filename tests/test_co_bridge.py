import os
import sys
import json
from datetime import datetime

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


def _bridge(tmp_path):
    wb = tmp_path / "weld_control.xlsx"
    _write_fixture(wb)
    manager = WeldControlManager({
        "file_path": str(wb), "sheet_name": "焊口編號明細",
        "col_serial": "流水號", "col_weld_no": "焊口編號",
    })
    builder = ChangeOrderBuilder(lookup=WeldLookup(manager=manager), clock=_fixed_clock)
    return ChangeOrderBridge(builder=builder, attachments_root=tmp_path / "records")


def test_envelope_shape(tmp_path):
    res = _bridge(tmp_path).info()
    assert set(res) >= {"ok", "data", "error"}
    assert res["ok"] is True and res["data"]["api_version"]


def test_existing_welds_filters_install_rows(tmp_path):
    res = _bridge(tmp_path).existing_welds("0100")
    assert res["ok"] is True
    nos = [w["weld_no"] for w in res["data"]["welds"]]
    assert "5" in nos and "8V" not in nos          # 安裝列被濾
    row5 = next(w for w in res["data"]["welds"] if w["weld_no"] == "5")
    assert row5["material"] == "SUS304" and row5["size"] == '2"'


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
            {"kind": "existing", "base": "5", "op": "加長"},
            {"kind": "new", "op": "加長", "spec": {"size": '1"', "material": "SUS304"}},
        ],
    }
    res = _bridge(tmp_path).build(payload)
    assert res["ok"] is True
    co = res["data"]["co"]
    assert co["series"] == "100"                    # 邊界正規化
    assert [w["code"] for w in co["welds"]] == ["5b", "1001"]   # 既有重焊→5b、新→1001
    assert res["data"]["status"] == "待補"          # 還沒照片/pdf
    codes = {i["code"] for i in res["data"]["issues"]}
    assert "missing_before_photo" in codes


def test_export_blocks_when_not_complete_then_succeeds(tmp_path):
    b = _bridge(tmp_path)
    base = {
        "series": "100", "date": "20260624",
        "welds": [{"kind": "existing", "base": "5", "op": "加長"}],
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
