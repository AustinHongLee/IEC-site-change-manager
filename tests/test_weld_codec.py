import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from change_order import Op, Origin, WeldEvent  # noqa: E402
from weld_codec import (  # noqa: E402
    ParsedCode,
    assign_event,
    next_new,
    next_rework,
    parse,
)


def test_parse_original_rework_new_and_w_prefix_codes():
    assert parse("2") == ParsedCode(base="2", rework_seq=0, is_new=False, raw="2", parsed=True)
    assert parse("2a") == ParsedCode(base="2", rework_seq=1, is_new=False, raw="2a", parsed=True)
    assert parse("2b") == ParsedCode(base="2", rework_seq=2, is_new=False, raw="2b", parsed=True)
    assert parse("1001") == ParsedCode(base=None, rework_seq=0, is_new=True, raw="1001", parsed=True)
    assert parse("w15") == ParsedCode(base="15", rework_seq=0, is_new=False, raw="w15", parsed=True)
    assert parse("w15a") == ParsedCode(base="15", rework_seq=1, is_new=False, raw="w15a", parsed=True)


def test_parse_malformed_code_keeps_raw_without_raising():
    assert parse("@@") == ParsedCode(base=None, rework_seq=0, is_new=False, raw="@@", parsed=False)


def test_next_rework_uses_highest_existing_rework_sequence():
    assert next_rework("2", ["1", "2", "2a"]) == ("2b", 2)
    assert next_rework("5", ["5"]) == ("5a", 1)
    assert next_rework("X", ["1", "2"]) == ("Xa", 1)
    assert next_rework("w15", ["w15", "15a"]) == ("15b", 2)


def test_next_rework_output_parses_back_to_same_base_and_sequence():
    code, seq = next_rework("2", ["2", "2a", "2b"])
    parsed = parse(code)

    assert code == "2c"
    assert parsed.base == "2"
    assert parsed.rework_seq == seq == 3


def test_next_new_uses_1000_floor_and_existing_numeric_max():
    assert next_new(["1", "2", "16"]) == "1001"
    assert next_new(["1", "1001"]) == "1002"


def test_next_new_uses_exists_callback_as_final_collision_check():
    occupied = {"1001", "1002"}

    assert next_new(["1", "2"], exists=occupied.__contains__) == "1003"


def test_assign_event_returns_copy_for_existing_event():
    event = WeldEvent(origin=Origin.EXISTING, base="2", op=Op.CUT)

    assigned = assign_event(event, ["1", "2", "2a"])

    assert assigned is not event
    assert assigned.code == "2b"
    assert assigned.rework_index == 2
    assert event.code is None
    assert event.rework_index is None


def test_assign_event_returns_copy_for_new_event():
    event = WeldEvent(origin=Origin.NEW, op=Op.EXTEND, rework_index=99)

    assigned = assign_event(event, ["1", "2", "1001"])

    assert assigned is not event
    assert assigned.code == "1002"
    assert assigned.rework_index is None
    assert event.code is None
    assert event.rework_index == 99


def test_weld_codec_import_is_headless_and_pure():
    control_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "control"))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {control_dir!r}); "
                "import weld_codec; "
                "names = ['PyQt6', 'weld_lookup', 'weld_control', 'openpyxl']; "
                "print({name: name in sys.modules for name in names})"
            ),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "{'PyQt6': False, 'weld_lookup': False, 'weld_control': False, 'openpyxl': False}"
