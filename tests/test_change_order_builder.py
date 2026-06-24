import os
import subprocess
import sys
from datetime import datetime

from openpyxl import Workbook

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from change_order import (  # noqa: E402
    JointType,
    Op,
    Role,
    Scenario,
    Spec,
    SpecSource,
    Status,
)
from change_order_builder import ChangeOrderBuilder  # noqa: E402
from weld_control import WeldControlManager  # noqa: E402
from weld_lookup import WeldLookup  # noqa: E402


class FixtureLookup(WeldLookup):
    def lookup_dwg_no(self, series):
        rows = self.manager.get_all_welds_by_serial(str(series).lstrip("0") or "0")
        return rows[0].get("圖號") if rows else None


def _fixed_clock():
    return datetime(2026, 6, 24, 8, 30, 5)


def _write_weld_control_fixture(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "焊口編號明細"
    ws.append(["流水號", "銲口編號", "尺寸", "厚度", "材質", "銲接型式", "屬性.1", "圖號"])
    ws.append([202, "2", '2"', "SCH40", "SUS304", "BW", "焊口", "DWG-202"])
    ws.append([202, "2a", '2"', "SCH40", "SUS304", "BW", "焊口", "DWG-202"])
    ws.append([202, "9", '3"', "SCH10", "SUS316", "RF", "VALVE安裝", "DWG-202"])
    ws.append([203, "1", '6"', "SCH80", "CS", "SW", "焊口", "DWG-203"])
    wb.save(path)
    wb.close()


def _builder_for_fixture(tmp_path):
    workbook = tmp_path / "weld_control.xlsx"
    _write_weld_control_fixture(workbook)
    manager = WeldControlManager({
        "file_path": str(workbook),
        "sheet_name": "焊口編號明細",
        "col_serial": "流水號",
        "col_weld_no": "焊口編號",
    })
    return ChangeOrderBuilder(lookup=FixtureLookup(manager=manager), clock=_fixed_clock)


def test_start_creates_draft_with_lookup_dwg_no_and_fixed_audit_time(tmp_path):
    builder = _builder_for_fixture(tmp_path)

    co = builder.start("0202", "20260624", scenario=Scenario.GROUP)

    assert co.status == Status.DRAFT
    assert co.series == "0202"
    assert co.dwg_no == "DWG-202"
    assert co.scenario == Scenario.GROUP
    assert len(co.audit.history) == 1
    assert co.audit.history[0].action == "created"
    assert co.audit.history[0].when == "2026-06-24T08:30:05"


def test_add_existing_weld_looks_up_spec_and_assigns_next_rework_code(tmp_path):
    builder = _builder_for_fixture(tmp_path)
    co = builder.start("0202", "20260624")

    event = builder.add_existing_weld(co, "2", Op.EXTEND)

    assert event.code == "2b"
    assert event.rework_index == 2
    assert event.spec == Spec(size='2"', sch="SCH40", material="SUS304", weld_type="BW")
    assert event.spec_source == SpecSource.LOOKED_UP
    assert co.welds == [event]


def test_add_existing_weld_uses_manual_spec_source_when_lookup_misses(tmp_path):
    builder = _builder_for_fixture(tmp_path)
    co = builder.start("0202", "20260624")

    event = builder.add_existing_weld(co, "99", Op.CUT, joint_type=JointType.THREAD)

    assert event.code == "99a"
    assert event.spec == Spec()
    assert event.spec_source == SpecSource.MANUAL
    assert event.joint_type == JointType.THREAD


def test_add_new_welds_merge_current_order_codes_to_avoid_collision(tmp_path):
    builder = _builder_for_fixture(tmp_path)
    co = builder.start("0202", "20260624")

    first = builder.add_new_weld(co, Op.EXTEND, Spec(size='1"', material="SUS304"))
    second = builder.add_new_weld(co, Op.EXTEND, {"size": '3"', "material": "CS"})

    assert first.code == "1001"
    assert second.code == "1002"
    assert first.spec_source == SpecSource.MANUAL
    assert second.spec_source == SpecSource.MANUAL
    assert [w.code for w in co.welds] == ["1001", "1002"]


def test_validate_reports_hard_bottom_missing_items_and_clears_after_fill(tmp_path):
    builder = _builder_for_fixture(tmp_path)
    co = builder.start("0202", "20260624")

    issues = builder.validate(co)

    assert [issue["code"] for issue in issues] == [
        "missing_before_photo",
        "missing_after_photo",
        "missing_drawing_pdf",
    ]

    builder.add_photo(co, Role.BEFORE, "before.jpg")
    builder.add_photo(co, Role.AFTER, "after.jpg", weld_ref="2b")
    builder.set_drawing_pdf(co, "drawing.pdf")

    assert builder.validate(co) == []


def test_compute_status_updates_change_order_status(tmp_path):
    builder = _builder_for_fixture(tmp_path)
    co = builder.start("0202", "20260624")

    assert builder.compute_status(co) == Status.PARTIAL
    assert co.status == Status.PARTIAL

    builder.add_photo(co, "before", "before.jpg")
    builder.add_photo(co, "after", "after.jpg")
    builder.set_drawing_pdf(co, "drawing.pdf")

    assert builder.compute_status(co) == Status.COMPLETE
    assert co.status == Status.COMPLETE


def test_optional_required_fields_can_require_materials_and_authorization(tmp_path):
    builder = _builder_for_fixture(tmp_path)
    co = builder.start("0202", "20260624")
    builder.add_photo(co, Role.BEFORE, "before.jpg")
    builder.add_photo(co, Role.AFTER, "after.jpg")
    builder.set_drawing_pdf(co, "drawing.pdf")

    assert [issue["code"] for issue in builder.validate(co, required=["materials", "authorization"])] == [
        "missing_materials",
        "missing_authorization",
    ]

    builder.add_material(co, component="Pipe", qty=2, unit="M")
    builder.set_authorization(co, approved_by="Owner", approved_at="2026-06-24")

    assert builder.validate(co, required=["materials", "authorization"]) == []


def test_finalize_id_uses_change_order_generate_id(tmp_path):
    builder = _builder_for_fixture(tmp_path)
    co = builder.start("202", "20260624")

    finalized = builder.finalize_id(co, ["202_20260624_01", "202_20260624_02"])

    assert finalized is co
    assert co.id == "202_20260624_03"


def test_change_order_builder_import_is_headless():
    control_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "control"))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {control_dir!r}); "
                "import change_order_builder; "
                "print('PyQt6' in sys.modules)"
            ),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
