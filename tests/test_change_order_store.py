import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from change_order import (  # noqa: E402
    ChangeOrder,
    DrawingPdf,
    Photo,
    Role,
    Status,
)
from change_order_store import export_change_order  # noqa: E402


def _write(path, data=b"x"):
    path.write_bytes(data)
    return path


def _sample_change_order(tmp_path):
    before = _write(tmp_path / "source_before.jpg", b"before")
    before_second = _write(tmp_path / "source_before_second.jpeg", b"before2")
    after = _write(tmp_path / "source_after.JPG", b"after")
    drawing = _write(tmp_path / "source_drawing.pdf", b"%PDF-1.4")
    co = ChangeOrder(
        id="88_20260624_01",
        status=Status.PARTIAL,
        date="20260624",
        series="88",
        photos=[
            Photo(role=Role.BEFORE, file=str(before)),
            Photo(role=Role.BEFORE, file=str(before_second)),
            Photo(role=Role.AFTER, file=str(after)),
        ],
        drawing_pdf=DrawingPdf(file=str(drawing)),
    )
    return co, before, before_second, after, drawing


def test_export_change_order_copies_files_and_rewrites_record_refs(tmp_path):
    co, before, before_second, after, drawing = _sample_change_order(tmp_path)
    root = tmp_path / "attachments"

    result = export_change_order(co, root)

    assert result.folder == root / "88_20260624_01"
    assert result.record_path == result.folder / "change_order.json"
    assert (result.folder / "before_1.jpg").read_bytes() == before.read_bytes()
    assert (result.folder / "before_2.jpeg").read_bytes() == before_second.read_bytes()
    assert (result.folder / "after_1.JPG").read_bytes() == after.read_bytes()
    assert (result.folder / "drawing.pdf").read_bytes() == drawing.read_bytes()
    assert result.copied == [
        (str(before), "before_1.jpg"),
        (str(before_second), "before_2.jpeg"),
        (str(after), "after_1.JPG"),
        (str(drawing), "drawing.pdf"),
    ]
    assert result.missing == []

    loaded = ChangeOrder.load_json(result.record_path)
    assert [photo.file for photo in loaded.photos] == ["before_1.jpg", "before_2.jpeg", "after_1.JPG"]
    assert loaded.drawing_pdf.file == "drawing.pdf"


def test_export_change_order_does_not_mutate_input_change_order(tmp_path):
    co, before, before_second, after, drawing = _sample_change_order(tmp_path)
    original_files = [photo.file for photo in co.photos]
    original_drawing = co.drawing_pdf.file

    export_change_order(co, tmp_path / "attachments")

    assert [photo.file for photo in co.photos] == original_files
    assert co.drawing_pdf.file == original_drawing
    assert original_files == [str(before), str(before_second), str(after)]
    assert original_drawing == str(drawing)


def test_export_change_order_records_missing_sources_without_failing(tmp_path):
    existing = _write(tmp_path / "source_before.jpg", b"before")
    missing = tmp_path / "missing_after.jpg"
    missing_pdf = tmp_path / "missing.pdf"
    co = ChangeOrder(
        id="88_20260624_02",
        photos=[
            Photo(role=Role.BEFORE, file=str(existing)),
            Photo(role=Role.AFTER, file=str(missing)),
        ],
        drawing_pdf=DrawingPdf(file=str(missing_pdf)),
    )

    result = export_change_order(co, tmp_path / "attachments")

    assert (result.folder / "before_1.jpg").exists()
    assert not (result.folder / "after_1.jpg").exists()
    assert not (result.folder / "drawing.pdf").exists()
    assert result.copied == [(str(existing), "before_1.jpg")]
    assert result.missing == [str(missing), str(missing_pdf)]

    loaded = ChangeOrder.load_json(result.record_path)
    assert [photo.file for photo in loaded.photos] == ["before_1.jpg", str(missing)]
    assert loaded.drawing_pdf.file == str(missing_pdf)


def test_export_change_order_requires_id(tmp_path):
    with pytest.raises(ValueError, match="id is required"):
        export_change_order(ChangeOrder(), tmp_path / "attachments")


def test_export_change_order_overwrite_policy(tmp_path):
    co, *_ = _sample_change_order(tmp_path)
    root = tmp_path / "attachments"

    first = export_change_order(co, root)
    with pytest.raises(FileExistsError):
        export_change_order(co, root)

    second = export_change_order(co, root, overwrite=True)
    assert second.record_path == first.record_path


def test_change_order_store_import_is_headless_and_pure():
    control_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "control"))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {control_dir!r}); "
                "import change_order_store; "
                "names = ['PyQt6', 'weld_lookup', 'weld_codec']; "
                "print({name: name in sys.modules for name in names})"
            ),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "{'PyQt6': False, 'weld_lookup': False, 'weld_codec': False}"
