# -*- coding: utf-8 -*-
"""test_change_order.py - 修改單記錄資料層（Task 1）測試。"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from change_order import (  # noqa: E402
    SCHEMA_VERSION,
    Audit,
    AuditEntry,
    Authorization,
    ChangeOrder,
    DrawingPdf,
    JointType,
    Material,
    Op,
    Origin,
    Photo,
    Role,
    Scenario,
    SpecSource,
    Status,
    WeldEvent,
    Spec,
    generate_id,
)


def _sample() -> ChangeOrder:
    """一張內容算完整的修改單，盡量踩到各種欄位 / Enum。"""
    return ChangeOrder(
        id="202_20260623_01",
        status=Status.COMPLETE,
        date="20260623",
        series="202",
        dwg_no="P-202-REV-A",
        scenario=Scenario.NORMAL,
        welds=[
            WeldEvent(
                joint_type=JointType.WELD,
                origin=Origin.EXISTING,
                base="2",
                op=Op.REWORK,
                rework_index=1,
                code="2a",
                spec=Spec(size="6\"", sch="STD", material="A106-B", weld_type="BW"),
                spec_source=SpecSource.LOOKED_UP,
            ),
            WeldEvent(
                joint_type=JointType.THREAD,
                origin=Origin.NEW,
                base=None,
                op=Op.NEW,
                code="1001",
                spec=Spec(size="2\""),
                spec_source=SpecSource.MANUAL,
            ),
        ],
        photos=[
            Photo(role=Role.BEFORE, file="before_01.jpg"),
            Photo(role=Role.AFTER, file="after_01.jpg", weld_ref="2a"),
        ],
        drawing_pdf=DrawingPdf(file="P-202.pdf", annotations=[{"x": 0.1, "y": 0.2}]),
        reason="管線干涉，需裁切重焊並新增一段",
        materials=[
            Material(component="elbow", component_id="E-90-6", size="6\"",
                     schedule="STD", material="A234", qty=2, unit="個", remark="90度"),
        ],
        authorization=Authorization(approved_by="王主任", approved_at="20260623",
                                     evidence="signed.pdf"),
    )


# --------------------------------------------------------------------------- #
# round-trip
# --------------------------------------------------------------------------- #
def test_roundtrip_dict():
    co = _sample()
    assert ChangeOrder.from_dict(co.to_dict()) == co


def test_roundtrip_json_file(tmp_path):
    co = _sample()
    path = tmp_path / "co.json"
    co.save_json(path)
    assert ChangeOrder.load_json(path) == co


def test_empty_changeorder_roundtrips():
    co = ChangeOrder()
    assert ChangeOrder.from_dict(co.to_dict()) == co


# --------------------------------------------------------------------------- #
# schema_version
# --------------------------------------------------------------------------- #
def test_schema_version_default():
    assert ChangeOrder().schema_version == SCHEMA_VERSION == "0.2"


def test_schema_version_always_in_output():
    out = ChangeOrder().to_dict()
    assert out["schema_version"] == SCHEMA_VERSION


def test_schema_version_missing_in_input_gets_default():
    co = ChangeOrder.from_dict({"id": "x"})
    assert co.schema_version == SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# 前向相容：缺欄位 / 多欄位 / 未知 Enum 值
# --------------------------------------------------------------------------- #
def test_missing_fields_get_defaults():
    co = ChangeOrder.from_dict({})
    assert co.status == Status.DRAFT
    assert co.scenario == Scenario.NORMAL
    assert co.welds == [] and co.photos == [] and co.materials == []
    assert co.drawing_pdf is None and co.authorization is None
    assert isinstance(co.audit, Audit) and co.audit.history == []


def test_unknown_fields_are_ignored():
    co = ChangeOrder.from_dict({"id": "x", "未來欄位": 123, "extra": {"a": 1}})
    assert co.id == "x"
    assert "未來欄位" not in co.to_dict()


def test_unknown_enum_value_is_tolerated_not_crash():
    # 未來新增的 op 值，舊程式載入不可崩，保留原字串
    data = WeldEvent(op=Op.REWORK).to_dict()
    data["op"] = "鑽孔"          # 未知 op
    data["origin"] = "未知來源"   # 未知 origin
    we = WeldEvent.from_dict(data)
    assert we.op == "鑽孔"
    assert we.origin == "未知來源"
    # 仍可再序列化回去（原字串保留）
    assert we.to_dict()["op"] == "鑽孔"


def test_changeorder_unknown_status_tolerated():
    co = ChangeOrder.from_dict({"status": "封存"})
    assert co.status == "封存"


# --------------------------------------------------------------------------- #
# Enum 序列化：JSON 內為中文 value，非 member name
# --------------------------------------------------------------------------- #
def test_enum_serialized_as_value():
    co = _sample()
    d = co.to_dict()
    assert d["status"] == "完整"
    assert d["scenario"] == "normal"
    assert d["welds"][0]["op"] == "重焊"
    assert d["welds"][0]["joint_type"] == "焊口"
    assert d["welds"][1]["joint_type"] == "管牙"
    assert d["welds"][0]["origin"] == "existing"
    assert d["welds"][0]["spec_source"] == "looked_up"
    assert d["photos"][0]["role"] == "before"


def test_enum_value_in_json_text_not_member_name():
    co = _sample()
    text = json.dumps(co.to_dict(), ensure_ascii=False)
    assert "重焊" in text and "完整" in text
    assert "Op.CUT" not in text and "Status.COMPLETE" not in text


def test_enum_value_reverse_lookup():
    co = ChangeOrder.from_dict({"status": "完整", "scenario": "group",
                                "welds": [{"op": "縮短", "origin": "existing", "joint_type": "管牙"},
                                          {"op": "加長", "origin": "new"}]})
    assert co.status is Status.COMPLETE
    assert co.scenario is Scenario.GROUP
    assert co.welds[0].op is Op.REWORK
    assert co.welds[0].joint_type is JointType.THREAD
    assert co.welds[1].op is Op.NEW


# --------------------------------------------------------------------------- #
# audit 軌跡（history[]），非單一時間戳
# --------------------------------------------------------------------------- #
def test_audit_is_history_not_timestamp():
    co = ChangeOrder()
    assert co.to_dict()["audit"] == {"history": []}


def test_audit_history_accumulates_and_roundtrips():
    co = ChangeOrder()
    co.audit.record("created", who="李工", detail={"src": "wizard"})
    co.audit.record("status_changed", who="李工", detail={"from": "草稿", "to": "完整"})
    assert len(co.audit.history) == 2
    loaded = ChangeOrder.from_dict(co.to_dict())
    assert loaded.audit.history == co.audit.history
    assert loaded.audit.history[0].action == "created"
    assert loaded.audit.history[1].detail == {"from": "草稿", "to": "完整"}


def test_audit_entry_make_stamps_time():
    e = AuditEntry.make("x", who="a")
    assert e.when is not None and e.action == "x" and e.who == "a"


# --------------------------------------------------------------------------- #
# generate_id
# --------------------------------------------------------------------------- #
def test_generate_id_first():
    assert generate_id("202", "20260623", []) == "202_20260623_01"


def test_generate_id_none_existing():
    assert generate_id("202", "20260623", None) == "202_20260623_01"


def test_generate_id_increments_same_series_date():
    existing = ["202_20260623_01", "202_20260623_02"]
    assert generate_id("202", "20260623", existing) == "202_20260623_03"


def test_generate_id_ignores_other_series_and_dates():
    existing = ["202_20260623_01", "999_20260623_05", "202_20260622_09"]
    assert generate_id("202", "20260623", existing) == "202_20260623_02"


def test_generate_id_two_digit_padding_and_beyond():
    assert generate_id("1", "20260101", ["1_20260101_08"]) == "1_20260101_09"
    big = [f"1_20260101_{n:02d}" for n in range(1, 100)]  # 到 _99
    assert generate_id("1", "20260101", big) == "1_20260101_100"


# --------------------------------------------------------------------------- #
# JSON 檔案：UTF-8 / ensure_ascii=False / 原子寫入結果
# --------------------------------------------------------------------------- #
def test_save_json_is_utf8_unescaped(tmp_path):
    path = tmp_path / "co.json"
    _sample().save_json(path)
    raw = path.read_text(encoding="utf-8")
    assert "重焊" in raw          # 中文不被 \uXXXX 轉義
    assert "\\u" not in raw
    # 確認是合法 JSON 且無殘留 .tmp
    json.loads(raw)
    assert not (tmp_path / "co.json.tmp").exists()
