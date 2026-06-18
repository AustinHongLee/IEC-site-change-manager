# -*- coding: utf-8 -*-

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter


def test_render_pdf_overlay_cli_creates_pdf(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    base_pdf = tmp_path / "base.pdf"
    output = tmp_path / "rendered.pdf"
    image = tmp_path / "before.png"
    template_path = tmp_path / "template.json"
    report_set_path = tmp_path / "report_set.json"

    writer = PdfWriter()
    writer.add_blank_page(width=400, height=300)
    with open(base_pdf, "wb") as f:
        writer.write(f)
    Image.new("RGB", (80, 50), (80, 140, 220)).save(image)
    report_set_path.write_text(
        json.dumps({
            "reports": [{
                "report": {"report_id": "R-CLI-PDF", "folder": "pdf_case"},
                "photos": {"before": [{"path": str(image)}]},
                "materials": {"rows": [{"component": "Pipe", "qty": 3, "unit": "M"}]},
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    template_path.write_text(
        json.dumps({
            "kind": "pdf_overlay",
            "schema_version": "template_mapping.v1",
            "target_schema_version": "pdf_overlay.v1",
            "base_pdf": str(base_pdf),
            "coordinate_space": "normalized",
            "fields": [
                {"type": "text", "source": "report.report_id", "page": 1, "rect_norm": [0.05, 0.06, 0.35, 0.08], "overflow": "shrink"},
                {"type": "image", "source": "photos.before[0].path", "page": 1, "rect_norm": [0.05, 0.18, 0.35, 0.30], "fit": "contain"},
                {
                    "type": "table",
                    "source": "materials.rows",
                    "page": 1,
                    "rect_norm": [0.05, 0.56, 0.60, 0.25],
                    "rows_per_page": 4,
                    "overflow": "new_page",
                    "columns": ["component", "qty", "unit"],
                },
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "render_pdf_overlay.py"),
            str(template_path),
            str(output),
            "--report-set",
            str(report_set_path),
            "--json",
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["renderer"]["kind"] == "pdf_overlay"
    assert data["outputs"][0]["kind"] == "pdf_overlay"
    assert output.exists()
    assert "R-CLI-PDF" in (PdfReader(str(output)).pages[0].extract_text() or "")
