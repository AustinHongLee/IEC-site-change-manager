import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from co_main_bridge import MainBridge  # noqa: E402


def _write(root, name, obj):
    rec = root / "records"
    rec.mkdir(exist_ok=True)
    (rec / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def test_info_envelope(tmp_path):
    res = MainBridge(tmp_path).info()
    assert set(res) >= {"ok", "data", "error"}
    assert res["ok"] is True and res["data"]["api_version"]


def test_pricebook_maps_real_columns(tmp_path):
    _write(tmp_path, "material_pricebook.json", {"items": [
        {"id": 'Pipe|2"', "零件類型": "Pipe (管)", "尺寸": '2"', "SCH": "SCH 40",
         "材質": "白鐵 (Stainless Steel)", "類別": "材料", "單位": "M",
         "單價": "100", "來源": "合約", "生效日": "", "備註": "ok"},
        {"id": "valve|3", "零件類型": "Valve", "尺寸": '3"', "SCH": "150#",
         "材質": "CS", "類別": "閥件", "單位": "EA", "單價": "", "來源": "", "生效日": "", "備註": ""},
    ]})
    res = MainBridge(tmp_path).pricebook()
    assert res["ok"] is True
    rows = res["data"]
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["part"] == "Pipe (管)" and r0["size"] == '2"' and r0["sch"] == "SCH 40"
    assert r0["mat"] == "白鐵 (Stainless Steel)" and r0["cat"] == "材料" and r0["unit"] == "M"
    assert r0["src"] == "合約" and r0["remark"] == "ok"
    assert "price" not in r0              # 已去價：橋不再回傳單價


def test_pricebook_missing_file_returns_empty(tmp_path):
    res = MainBridge(tmp_path).pricebook()
    assert res["ok"] is True and res["data"] == []


def test_records_empty_store(tmp_path):
    _write(tmp_path, "records.json", {"records": [], "details": [], "materials": []})
    res = MainBridge(tmp_path).records()
    assert res["ok"] is True and res["data"] == []


def test_project_parts_register_unregister(tmp_path):
    b = MainBridge(tmp_path)
    assert b.project_parts()["data"]["registered"] == []          # 起始空
    r = b.register_parts(["0001", "0005", "0001"])                # 去重
    assert r["ok"] and set(r["data"]["registered"]) == {"0001", "0005"}
    r2 = b.unregister_parts(["0001"])
    assert r2["data"]["registered"] == ["0005"]
    # 換一個 bridge 實例仍讀得到 → 已持久化到 project_parts.json
    assert MainBridge(tmp_path).project_parts()["data"]["registered"] == ["0005"]
