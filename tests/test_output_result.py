# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from output_result import attach_output_envelope, build_output_result, output_item, step_item


def test_build_output_result_creates_stable_envelope(tmp_path):
    output = tmp_path / "out.xlsx"
    output.write_text("demo", encoding="utf-8")

    result = build_output_result(
        ok=True,
        outputs=[output_item(kind="xlsx_template", path=output, label="Workbook")],
        issues=[],
        capabilities={"renderer": {"kind": "xlsx_template"}},
        steps=[step_item(key="render", ok=True)],
    )

    assert result["result_schema_version"] == "output_result.v1"
    assert result["outputs"][0]["kind"] == "xlsx_template"
    assert result["outputs"][0]["exists"] is True
    assert result["capabilities"]["renderer"]["kind"] == "xlsx_template"
    assert result["steps"][0]["ok"] is True


def test_attach_output_envelope_keeps_renderer_specific_fields(tmp_path):
    raw = {"ok": False, "path": "", "summary": {"text": 1}, "issues": [{"code": "x"}]}

    result = attach_output_envelope(raw, outputs=[output_item(kind="pdf", path="", optional=True)])

    assert result is raw
    assert result["result_schema_version"] == "output_result.v1"
    assert result["summary"] == {"text": 1}
    assert result["issues"][0]["code"] == "x"
