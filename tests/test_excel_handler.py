# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

import excel_handler


class _FakeRange:
    def __init__(self):
        self.NumberFormat = ""
        self.Value = ""


class _FakeSheet:
    def Range(self, _name):
        return _FakeRange()

    def Activate(self):
        return None


class _FakeWorkbook:
    Name = "template.xlsm"

    def __init__(self, output_bytes: bytes):
        self._sheet = _FakeSheet()
        self._output_bytes = output_bytes

    def Sheets(self, _name):
        return self._sheet

    def Activate(self):
        return None

    def SaveAs(self, output_file, FileFormat=None):
        Path(output_file).write_bytes(self._output_bytes)

    def Close(self, SaveChanges=False):
        return None


class _FakeWorkbooks:
    def __init__(self, output_bytes: bytes):
        self._output_bytes = output_bytes

    def Open(self, _path):
        return _FakeWorkbook(self._output_bytes)


class _FakeExcel:
    def __init__(self, output_bytes: bytes):
        self.Workbooks = _FakeWorkbooks(output_bytes)
        self.Application = self
        self.calls = []

    def Goto(self, *_args, **_kwargs):
        return None

    def Run(self, *_args, **_kwargs):
        self.calls.append(_args)
        return None


class _FakeExcelManager:
    def __init__(self, output_bytes: bytes):
        self.excel = _FakeExcel(output_bytes)


class _Token:
    code = "1r"


def test_generate_report_no_pdf_validates_xlsm_only(monkeypatch, tmp_path):
    output_dir = tmp_path / "output"
    pdf_dir = tmp_path / "pdf"
    folder = tmp_path / "attachments" / "20260112" / "0547_AG"
    output_dir.mkdir(parents=True)
    pdf_dir.mkdir(parents=True)
    folder.mkdir(parents=True)
    (folder / "before.jpg").write_bytes(b"fake image")
    fake_manager = _FakeExcelManager(b"x" * 1024)

    monkeypatch.setattr(excel_handler.RUNTIME, "export_pdf", False)
    monkeypatch.setattr(
        excel_handler,
        "get_excel_manager",
        lambda: fake_manager,
    )
    monkeypatch.setattr(
        excel_handler,
        "get_template_for_mode",
        lambda _mode, _count: {
            "path": str(tmp_path / "template.xlsm"),
            "sheet": "template",
            "id_cell": "AD3",
            "date_cell": "AD4",
            "series_cell": "AD5",
            "line_cell": "G4",
            "dwg_cell": "G5",
            "desc_cell": "G7",
            "before_range": "C9:AI23",
            "after_range": "C24:AI38",
            "weld_slots": ["G6"],
        },
    )

    result = excel_handler.generate_report(
        folder_path=str(folder),
        folder_name="0547_AG",
        date_str="20260112",
        series_no="0547",
        mode="single",
        tokens=[_Token()],
        note_text="",
        materials_text="",
        line_number="",
        dwg_no="",
        report_id="20260112-01",
        seq=1,
        output_dir=str(output_dir),
        pdf_dir=str(pdf_dir),
        description="no pdf smoke",
    )

    assert result.success is True
    assert result.output_file
    assert Path(result.output_file).exists()
    assert result.pdf_file is None
    assert not list(pdf_dir.glob("*.pdf"))
    assert fake_manager.excel.calls[0][0] == "'template.xlsm'!InsertAndFitPicture_ByAddr"
