import os
import sys
import json
import base64

from PIL import Image
from pypdf import PdfWriter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from co_main_bridge import MainBridge  # noqa: E402
from material_taxonomy import material_family, normalize_material, normalize_schedule, normalize_size  # noqa: E402


def _write(root, name, obj):
    rec = root / "records"
    rec.mkdir(exist_ok=True)
    (rec / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _write_root_json(root, name, obj):
    (root / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _write_pdf(path):
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as f:
        writer.write(f)


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
    assert r0["part"] == "Pipe (管)" and r0["size"] == "DN50" and r0["sch"] == "SCH40"
    assert r0["mat"] == "白鐵 (STAINLESS STEEL)" and r0["cat"] == "管材" and r0["unit"] == "M"
    assert r0["icon"] == "Pipe" and r0["material_family"] == "通用白鐵"
    assert r0["src"] == "合約" and r0["remark"] == "ok"
    assert "price" not in r0              # 已去價：橋不再回傳單價


def test_pricebook_missing_file_returns_empty(tmp_path):
    res = MainBridge(tmp_path).pricebook()
    assert res["ok"] is True and res["data"] == []


def test_material_taxonomy_api_exposes_axes_and_fasteners(tmp_path):
    res = MainBridge(tmp_path).material_taxonomy()

    assert res["ok"] is True
    data = res["data"]
    sizes = data["axes"]["nominal_diameter"]["values"]
    assert sizes[0] == "DN15" and sizes[-1] == "DN500"
    assert {"螺栓", "螺帽", "華司", "U型螺栓"} <= set(data["options"]["cat"])
    assert any(p["code"] == "bolt" and "螺絲" in p["aliases"] for p in data["part_types"])


def test_pricebook_enriches_taxonomy_fields(tmp_path):
    _write(tmp_path, "material_pricebook.json", {"items": [
        {"id": "b1", "零件類型": "STUD BOLT", "尺寸": "", "SCH": "", "材質": "HDG",
         "類別": "", "單位": "", "來源": "", "備註": ""},
        {"id": "p1", "零件類型": "PIPE", "尺寸": '2"', "SCH": "S-40", "材質": "A106-B",
         "類別": "配管", "單位": "M", "來源": "", "備註": ""},
        {"id": "TYPE07-SLIDE-150X150X3T-AS", "零件類型": "Type07 滑板", "尺寸": "150x150x3t",
         "SCH": "", "材質": "A36/SS400", "類別": "滑板", "單位": "片", "來源": "",
         "備註": "", "Type": "Type07", "支撐級別": "零件", "規格": "Type07,Type07 滑板,150x150x3t,A36/SS400"},
    ]})

    rows = MainBridge(tmp_path).pricebook()["data"]

    assert rows[0]["cat"] == "螺栓"
    assert rows[0]["icon"] == "BoltNut"
    assert rows[0]["material_family"] == "鍍鋅"
    assert rows[1]["part"] == "PIPE"
    assert rows[1]["size"] == "DN50"
    assert rows[1]["sch"] == "SCH40"
    assert rows[1]["mat"] == "A106 GR.B"
    assert rows[1]["cat"] == "管材"
    assert rows[1]["material_family"] == "通用黑鐵"
    assert rows[2]["type"] == "Type07"
    assert rows[2]["level"] == "零件"
    assert rows[2]["spec"] == "Type07,Type07 滑板,150x150x3t,A36/SS400"


def test_material_normalizers_cover_common_site_aliases():
    assert normalize_size('2"') == "DN50"
    assert normalize_size("DN80x15") == "DN80xDN15"
    assert normalize_size("L50*50*6") == "L50x50x6"
    assert normalize_size("M16x50") == "M16x50"
    assert normalize_size("1219x2438x12t") == "1219x2438x12t"
    assert normalize_schedule("S-40") == "SCH40"
    assert normalize_schedule("150LB") == "150#"
    assert normalize_schedule("CLASS150") == "150#"
    assert normalize_material("A182-F304.") == "A182 F304"
    assert material_family("A234 GR.WPB") == "通用黑鐵"
    assert material_family("A36/SS400") == "通用黑鐵"


def test_records_missing_attachments(tmp_path):
    assert MainBridge(tmp_path).records()["data"] == []


def test_weld_table_setting_round_trips_to_settings_json(tmp_path):
    _write_root_json(tmp_path, "settings.json", {
        "paths": {"weld_control_table": "old.xlsx", "drawing_list": "dwg.xlsx"},
        "meta": {"version": "test"},
    })
    b = MainBridge(tmp_path)

    settings = b.app_settings()
    assert settings["ok"] is True
    assert settings["data"]["weld_control_table"] == "old.xlsx"

    res = b.save_setting("weld_control_table", "new-control.xlsx")
    assert res["ok"] is True
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["paths"]["weld_control_table"] == "new-control.xlsx"
    assert json.loads((tmp_path / "records" / "app_settings.json").read_text(encoding="utf-8"))[
        "weld_control_table"
    ] == "new-control.xlsx"


def test_records_reads_change_orders(tmp_path):
    # 精靈出單：attachments/<id>/change_order.json → records() 映成前端記錄
    folder = tmp_path / "attachments" / "55_2026-07-01_01"
    folder.mkdir(parents=True)
    (folder / "before_1.jpg").write_bytes(b"jpg")
    (folder / "change_order.json").write_text(json.dumps({
        "id": "55_2026-07-01_01", "date": "2026-07-01", "series": "55",
        "status": "待補", "reason": "現場改管",
        "welds": [{"code": "1001", "op": "裁切",
                   "spec": {"size": "DN50", "sch": "SCH40", "material": "A106 GR.B"}}],
        "materials": [{"component_id": "0002", "component": "90°彎頭", "size": "DN50",
                       "schedule": "SCH40", "material": "A234 GR.WPB", "qty": 2,
                       "unit": "個", "remark": ""}],
        "photos": [{"role": "before", "file": "before_1.jpg"}],
    }, ensure_ascii=False), encoding="utf-8")
    res = MainBridge(tmp_path).records()
    assert res["ok"] is True and len(res["data"]) == 1
    r = res["data"][0]
    assert r["series"] == "55" and r["status"] == "pending" and r["reason"] == "現場改管"
    assert r["welds"][0] == {"code": "1001", "mark": "重焊", "size": "DN50",
                             "mat": "A106 GR.B", "sch": "SCH40", "coef": ""}
    assert r["mats"][0]["id"] == "0002"
    assert r["mats"][0]["part"] == "90°彎頭" and r["mats"][0]["qty"] == 2
    assert r["mats"][0]["unit"] == "個"
    assert r["photos"][0]["label"] == "修改前"
    assert r["photos"][0]["src"] == str((folder / "before_1.jpg").resolve())
    bill = MainBridge(tmp_path).billing()
    assert bill["ok"] and len(bill["data"]["rows"]) == 1
    assert bill["data"]["rows"][0]["status"] == "未請款"


def test_dates_include_change_order_drafts(tmp_path):
    folder = tmp_path / "attachments" / "55_2026-07-01_01"
    folder.mkdir(parents=True)
    (folder / "change_order.json").write_text(json.dumps({
        "id": "55_2026-07-01_01", "date": "2026-07-01", "series": "55",
        "status": "完整",
        "welds": [{"code": "1001", "spec": {}}, {"code": "1002", "spec": {}}],
    }, ensure_ascii=False), encoding="utf-8")

    res = MainBridge(tmp_path).dates()

    assert res["ok"] is True
    assert res["data"][0]["date"] == "20260701"
    item = res["data"][0]["items"][0]
    assert item["series"] == "55"
    assert item["welds"] == 2
    assert item["weld_codes"] == ["1001", "1002"]
    assert item["status"] == "done"
    assert item["record_id"] == "55_2026-07-01_01"
    assert item["source"] == "change_order"


def test_save_record_updates_change_order_json(tmp_path):
    folder = tmp_path / "attachments" / "55_20260701_01"
    folder.mkdir(parents=True)
    (folder / "change_order.json").write_text(json.dumps({
        "id": "55_20260701_01", "date": "20260701", "series": "55",
        "status": "完整",
        "welds": [{"code": "1001", "op": "加長", "spec": {"size": "DN50", "sch": "SCH40", "material": "CS"}}],
        "materials": [],
    }, ensure_ascii=False), encoding="utf-8")
    rec = MainBridge(tmp_path).records()["data"][0]
    rec["welds"][0]["size"] = "DN80"
    rec["welds"][0]["mat"] = "A106 GR.B"
    rec["mats"].append({
        "id": "0002", "part": "90°彎頭", "size": "DN80", "sch": "SCH40",
        "mat": "A234 WPB", "qty": "2", "unit": "個", "remark": "現場追加",
    })

    res = MainBridge(tmp_path).save_record(rec)

    assert res["ok"] is True
    saved = json.loads((folder / "change_order.json").read_text(encoding="utf-8"))
    assert saved["welds"][0]["spec"]["size"] == "DN80"
    assert saved["welds"][0]["op"] == "重焊"
    assert saved["welds"][0]["spec"]["material"] == "A106 GR.B"
    assert saved["materials"][0]["component_id"] == "0002"
    assert saved["materials"][0]["qty"] == 2
    assert saved["audit"]["history"][-1]["action"] == "saved_from_main"
    assert res["data"]["mats"][0]["unit"] == "個"


def test_open_record_folder_and_pdf_use_injected_opener(tmp_path):
    folder = tmp_path / "attachments" / "55_20260701_01"
    folder.mkdir(parents=True)
    (folder / "drawing.pdf").write_bytes(b"%PDF-1.4")
    (folder / "change_order.json").write_text(json.dumps({
        "id": "55_20260701_01",
        "drawing_pdf": {"file": "drawing.pdf"},
    }, ensure_ascii=False), encoding="utf-8")
    opened = []
    b = MainBridge(tmp_path)
    b._open_path_fn = opened.append

    folder_res = b.open_record_folder("55_20260701_01")
    pdf_res = b.open_record_pdf("55_20260701_01")

    assert folder_res["ok"] and folder_res["data"]["path"] == str(folder)
    assert pdf_res["ok"] and pdf_res["data"]["path"] == str(folder / "drawing.pdf")
    assert opened == [str(folder), str(folder / "drawing.pdf")]


def test_export_records_and_material_summary(tmp_path):
    folder = tmp_path / "attachments" / "55_20260701_01"
    folder.mkdir(parents=True)
    (folder / "change_order.json").write_text(json.dumps({
        "id": "55_20260701_01", "date": "20260701", "series": "55",
        "welds": [{"code": "1001", "spec": {}}],
        "materials": [{"component_id": "0002", "component": "90°彎頭", "qty": 2, "unit": "個"}],
    }, ensure_ascii=False), encoding="utf-8")
    b = MainBridge(tmp_path)
    records_path = tmp_path / "records.xlsx"
    mats_path = tmp_path / "materials.xlsx"

    rec_res = b.export_records(str(records_path))
    mat_res = b.export_record_materials(str(mats_path))

    assert rec_res["ok"] and rec_res["data"]["count"] == 1 and records_path.is_file()
    assert mat_res["ok"] and mat_res["data"]["count"] == 1 and mats_path.is_file()


def test_export_output_center_owner_data_package_from_selected_items(tmp_path):
    folder = tmp_path / "attachments" / "20260702" / "720_3r2_3a2"
    folder.mkdir(parents=True)
    (folder / "GroupWeld.txt").write_text("3r3\n3a3\n", encoding="utf-8")
    (folder / "note.txt").write_text("因現場管線干涉，切除原焊口並新增焊口。", encoding="utf-8")
    Image.new("RGB", (80, 160), (220, 80, 60)).save(folder / "before_1.jpg")
    Image.new("RGB", (180, 80), (80, 160, 90)).save(folder / "after_1.jpg")
    _write_pdf(folder / "720.CA-2007-100-AA1B-NA-1.pdf")

    res = MainBridge(tmp_path).export_output_center(
        "owner-data",
        [{"date": "20260702", "folder": "720_3r2_3a2", "series": "720"}],
    )

    assert res["ok"] is True
    files = res["data"]["files"]
    assert files["statistics_xlsx"] == ""
    assert files["owner_data_package"].endswith("owner_data_report")
    assert files["owner_data_index_xlsx"].endswith("owner_data_index.xlsx")
    assert (tmp_path / "staging" / "site_output_center_web" / "owner_data_report" / "CO-720-3r2-3a2").is_dir()


def test_export_output_center_owner_data_package_from_root_change_order_folder(tmp_path):
    folder = tmp_path / "attachments" / "107_20260701_01"
    folder.mkdir(parents=True)
    Image.new("RGB", (80, 160), (220, 80, 60)).save(folder / "before_1.jpg")
    Image.new("RGB", (180, 80), (80, 160, 90)).save(folder / "after_1.jpg")
    _write_pdf(folder / "drawing.pdf")
    (folder / "change_order.json").write_text(json.dumps({
        "schema_version": "0.2",
        "id": "107_20260701_01",
        "status": "完整",
        "date": "20260701",
        "series": "107",
        "welds": [{
            "origin": "existing",
            "op": "重焊",
            "base": "3",
            "code": "3a",
            "spec": {"size": "3", "sch": "S-40", "material": "C.S", "weld_type": "BW"},
        }],
        "materials": [{
            "component": "支撐管",
            "size": "DN40",
            "schedule": "SCH80",
            "material": "SUS304",
            "qty": 1,
            "unit": "米",
        }],
        "photos": [{"role": "before", "file": "before_1.jpg"}, {"role": "after", "file": "after_1.jpg"}],
        "drawing_pdf": {"file": "drawing.pdf"},
        "reason": "因管線干涉新增支撐。",
    }, ensure_ascii=False), encoding="utf-8")

    res = MainBridge(tmp_path).export_output_center(
        "owner-data",
        [{"date": "20260701", "folder": str(folder), "record_id": "107_20260701_01", "series": "107"}],
    )

    assert res["ok"] is True
    files = res["data"]["files"]
    report_set = json.loads(open(files["report_set"], encoding="utf-8").read())
    report = report_set["reports"][0]
    assert report["report"]["folder"] == "107_20260701_01"
    assert report["report"]["status"] != "missing_folder"
    assert report["welds"]["count"] == 1
    assert report["welds"]["summary"] == "3a（3 / C.S / S-40）（共1口）"
    assert report["materials"]["count"] == 1
    assert report["photos"]["has_before"] is True
    assert report["photos"]["has_after"] is True
    assert report["attachment_pdf"]["exists"] is True
    assert (tmp_path / "staging" / "site_output_center_web" / "owner_data_report" / "CO-107-20260701-01").is_dir()


def test_save_billing_status_round_trips(tmp_path):
    folder = tmp_path / "attachments" / "55_20260701_01"
    folder.mkdir(parents=True)
    (folder / "change_order.json").write_text(json.dumps({
        "id": "55_20260701_01", "date": "20260701", "series": "55",
    }, ensure_ascii=False), encoding="utf-8")
    b = MainBridge(tmp_path)

    res = b.save_billing([{"rec": 0, "status": "已請款", "billDate": "2026-07-01", "remark": "ok"}])
    bill = MainBridge(tmp_path).billing()

    assert res["ok"] and res["data"]["count"] == 1
    assert bill["data"]["rows"][0]["status"] == "已請款"
    assert bill["data"]["rows"][0]["billDate"] == "2026-07-01"
    assert bill["data"]["rows"][0]["remark"] == "ok"


def test_replace_photo_copies_file_and_updates_change_order(tmp_path):
    folder = tmp_path / "attachments" / "55_20260701_01"
    folder.mkdir(parents=True)
    (folder / "before_1.jpg").write_bytes(b"old")
    (folder / "change_order.json").write_text(json.dumps({
        "id": "55_20260701_01",
        "photos": [{"role": "before", "file": "before_1.jpg"}],
    }, ensure_ascii=False), encoding="utf-8")
    replacement = tmp_path / "replacement.png"
    replacement.write_bytes(b"new")

    res = MainBridge(tmp_path).replace_photo("55_20260701_01", 0, str(replacement))

    assert res["ok"] is True
    data = json.loads((folder / "change_order.json").read_text(encoding="utf-8"))
    assert data["photos"][0]["file"] == "before_1.png"
    assert (folder / "before_1.png").read_bytes() == b"new"
    assert res["data"]["photo"]["label"] == "修改前"
    assert res["data"]["photo"]["src"] == str((folder / "before_1.png").resolve())


def test_save_photo_annotation_writes_png_and_updates_change_order(tmp_path):
    folder = tmp_path / "attachments" / "55_20260701_01"
    folder.mkdir(parents=True)
    (folder / "after_1.jpg").write_bytes(b"old")
    (folder / "change_order.json").write_text(json.dumps({
        "id": "55_20260701_01",
        "photos": [{"role": "after", "file": "after_1.jpg"}],
    }, ensure_ascii=False), encoding="utf-8")
    raw = b"\x89PNG\r\n\x1a\nannotated"
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

    res = MainBridge(tmp_path).save_photo_annotation("55_20260701_01", 0, data_url)

    assert res["ok"] is True
    data = json.loads((folder / "change_order.json").read_text(encoding="utf-8"))
    assert data["photos"][0]["file"] == "after_1_annotated.png"
    assert (folder / "after_1_annotated.png").read_bytes() == raw
    assert res["data"]["photo"]["label"] == "修改後"


def test_image_data_url_accepts_record_photo_file_url(tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"jpg-bytes")

    res = MainBridge(tmp_path).image_data_url(photo.as_uri())

    assert res["ok"] is True
    assert res["data"]["url"].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(res["data"]["url"].split(",", 1)[1]) == b"jpg-bytes"


def test_project_parts_register_unregister(tmp_path):
    _write(tmp_path, "material_pricebook.json", {"items": [{"id": "0001"}, {"id": "0005"}]})
    b = MainBridge(tmp_path)
    assert b.project_parts()["data"]["registered"] == []          # 起始空
    r = b.register_parts(["0001", "0005", "0001"])                # 去重
    assert r["ok"] and set(r["data"]["registered"]) == {"0001", "0005"}
    r2 = b.unregister_parts(["0001"])
    assert r2["data"]["registered"] == ["0005"]
    # 換一個 bridge 實例仍讀得到 → 已持久化到 project_parts.json
    assert MainBridge(tmp_path).project_parts()["data"]["registered"] == ["0005"]


def test_project_parts_prunes_stale_ids_after_catalog_regeneration(tmp_path):
    _write(tmp_path, "material_pricebook.json", {"items": [{"id": "PIPE-DN15-S40-CS"}]})
    _write(tmp_path, "project_parts.json", {"registered": ["0001", "PIPE-DN15-S40-CS"]})

    res = MainBridge(tmp_path).project_parts()

    assert res["ok"] is True
    assert res["data"]["registered"] == ["PIPE-DN15-S40-CS"]
    assert res["data"]["dropped"] == ["0001"]
    saved = json.loads((tmp_path / "records" / "project_parts.json").read_text(encoding="utf-8"))
    assert saved["registered"] == ["PIPE-DN15-S40-CS"]


def test_upsert_project_parts_registers_custom_materials_and_pricebook(tmp_path):
    _write(tmp_path, "material_pricebook.json", {"items": [{"id": "PIPE-DN15-S40-CS", "零件類型": "PIPE"}]})
    b = MainBridge(tmp_path)
    support_pipe = {
        "id": "SUPPORT-01-2B-03C-01",
        "part": "支撐管",
        "size": "DN40",
        "sch": "SCH80",
        "mat": "SUS304",
        "qty": 0.171,
        "unit": "米",
        "cat": "管材",
        "type": "Type01",
        "level": "管架展開",
        "spec": '1-1/2"*SCH.80',
        "source_designation": "01-2B-03C",
        "remark": "from support calculator",
    }

    res = b.upsert_project_parts([support_pipe])

    assert res["ok"] is True
    assert res["data"]["added"] == ["SUPPORT-01-2B-03C-01"]
    project = b.project_parts()["data"]
    assert project["registered"] == ["SUPPORT-01-2B-03C-01"]
    assert project["custom"][0]["id"] == "SUPPORT-01-2B-03C-01"
    assert project["custom"][0]["project_only"] is True
    rows = b.pricebook()["data"]
    custom = next(r for r in rows if r["id"] == "SUPPORT-01-2B-03C-01")
    assert custom["part"] == "支撐管"
    assert custom["size"] == "DN40"
    assert custom["sch"] == "SCH80"
    assert custom["mat"] == "SUS304"
    assert custom["project_only"] is True
    assert custom["source_designation"] == "01-2B-03C"

    out = tmp_path / "project_parts.xlsx"
    export = b.export_project_parts(str(out))
    assert export["ok"] is True
    assert export["data"]["count"] == 1
    assert out.is_file()


def test_support_bom_expands_external_type_calculator_to_material_rows(tmp_path, monkeypatch):
    app = tmp_path / "for_iec_support" / "python_app"
    core = app / "core"
    core.mkdir(parents=True)
    (core / "__init__.py").write_text("", encoding="utf-8")
    (core / "calculator.py").write_text(
        """
class Entry:
    def __init__(self, item_no, name, spec, length, width, material, quantity, unit, category, role='', remark=''):
        self.item_no = item_no
        self.name = name
        self.spec = spec
        self.length = length
        self.width = width
        self.material = material
        self.quantity = quantity
        self.unit = unit
        self.category = category
        self.role = role
        self.remark = remark
        self.weight_output = 1.25 * item_no
        self.unit_weight = 1.25
        self.length_subtotal = length / 1000 if role == 'pipe' else 0
        self.qty_subtotal = quantity if role != 'pipe' else 0
        self.part_key = ''
        self.stock_id = ''
        self.item_class = ''
        self.manufacturing_type = 'raw_cut' if role == 'pipe' else 'plate_cut'

    @property
    def display_spec(self):
        return self.spec

    @property
    def display_remark(self):
        return self.remark


class Result:
    def __init__(self, fullstring):
        self.fullstring = fullstring
        self.error = ''
        self.warnings = []
        self.meta = {}
        self.entries = [
            Entry(1, '管路', '1-1/2"*SCH.80', 171, 0, 'SUS304', 1, 'M', '管路類', 'pipe'),
            Entry(2, 'Plate_a_無鑽孔', '9', 150, 150, 'A36/SS400', 1, 'PC', '鋼板類', 'base_plate'),
        ]

    @property
    def total_weight(self):
        return sum(e.weight_output for e in self.entries)


def analyze_single(fullstring, overrides=None):
    return Result(fullstring)
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CO_SUPPORT_APP_DIR", str(app))

    res = MainBridge(tmp_path).support_bom("01-2b-03c")

    assert res["ok"] is True
    data = res["data"]
    assert data["designation"] == "01-2B-03C"
    assert data["type"] == "01"
    assert data["total_weight"] == 3.75
    assert len(data["entries"]) == 2
    pipe, plate = data["materials"]
    assert pipe["part"] == "支撐管"
    assert pipe["size"] == "DN40"
    assert pipe["sch"] == "SCH80"
    assert pipe["qty"] == 0.171
    assert pipe["unit"] == "米"
    assert plate["cat"] == "底板"
    assert plate["size"] == "150x150x9t"
    assert plate["unit"] == "片"
    assert plate["type"] == "Type01"
