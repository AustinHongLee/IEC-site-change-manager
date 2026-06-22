# -*- coding: utf-8 -*-

import importlib.util
import sys
from datetime import datetime
from pathlib import Path


def load_record_ai_session():
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "record_ai_session",
        repo / "tools" / "record_ai_session.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_slugify_topic_keeps_readable_cjk_and_ascii():
    tool = load_record_ai_session()

    assert tool.slugify_topic("P0 Repo 護欄 / UI smoke!") == "P0-Repo-護欄-UI-smoke"


def test_today_string_accepts_injected_datetime():
    tool = load_record_ai_session()

    assert tool.today_string(datetime(2026, 6, 22, 8, 30)) == "2026-06-22"


def test_next_available_path_appends_suffix(tmp_path):
    tool = load_record_ai_session()
    first = tmp_path / "2026-06-22_codex_test.md"
    second = tmp_path / "2026-06-22_codex_test-2.md"
    first.write_text("x", encoding="utf-8")

    assert tool.next_available_path(tmp_path, first.name) == second


def test_build_session_markdown_contains_snapshot_and_bullets():
    tool = load_record_ai_session()
    snapshot = tool.GitSnapshot(
        branch_status="## main...origin/main",
        head="abc1234",
        recent_log="abc1234 test commit",
        diff_stat="<no working tree diff>",
    )

    content = tool.build_session_markdown(
        title="AI Session：P0",
        date="2026-06-22",
        role="工程實作",
        goal="建立黑盒紀錄",
        snapshot=snapshot,
        summaries=["新增 record_ai_session.py"],
        validations=["pytest passed"],
        risks=["只記錄摘要，不取代人工 review"],
        next_steps=["接到每次工作收尾流程"],
    )

    assert "# AI Session：P0" in content
    assert "- 新增 record_ai_session.py" in content
    assert "- pytest passed" in content
    assert "abc1234" in content
    assert "<no working tree diff>" in content
