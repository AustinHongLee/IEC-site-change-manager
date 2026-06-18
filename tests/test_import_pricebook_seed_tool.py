# -*- coding: utf-8 -*-

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_importer():
    path = Path(__file__).resolve().parents[1] / "tools" / "import_pricebook_seed.py"
    spec = importlib.util.spec_from_file_location("import_pricebook_seed_tool", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_import_plan_skips_existing_material_key():
    importer = _load_importer()
    current = {
        "items": [{
            "id": "existing",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "白鐵 (Stainless Steel)",
            "單位": "M",
            "單價": "",
        }]
    }
    seed = [
        {
            "id": "same-key",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 40",
            "材質": "SS",
            "單位": "M",
            "單價": "",
        },
        {
            "id": "new-key",
            "零件類型": "Pipe (管)",
            "尺寸": '2"',
            "SCH": "SCH 80",
            "材質": "白鐵 (Stainless Steel)",
            "單位": "M",
            "單價": "",
        },
    ]

    plan = importer.build_import_plan(seed, current)

    assert plan["existing_count"] == 1
    assert plan["candidate_count"] == 2
    assert len(plan["added"]) == 1
    assert len(plan["skipped"]) == 1
    assert plan["added"][0]["SCH"] == "SCH 80"


def test_cli_dry_run_does_not_create_target_file(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    seed_path = tmp_path / "seed.json"
    target_path = tmp_path / "material_pricebook.json"
    seed_path.write_text(
        json.dumps({
            "items": [{
                "id": "Pipe (管)|2\"|SCH 40|白鐵 (Stainless Steel)",
                "零件類型": "Pipe (管)",
                "尺寸": '2"',
                "SCH": "SCH 40",
                "材質": "白鐵 (Stainless Steel)",
                "單位": "M",
                "單價": "",
                "備註": "",
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo / "tools" / "import_pricebook_seed.py"),
            str(seed_path),
            "--target",
            str(target_path),
        ],
        cwd=repo,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "DRY-RUN" in result.stdout
    assert "將新增: 1" in result.stdout
    assert not target_path.exists()
