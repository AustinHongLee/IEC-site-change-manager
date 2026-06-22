# -*- coding: utf-8 -*-

import importlib.util
import sys
from pathlib import Path


def load_repo_guard():
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("repo_guard", repo / "tools" / "repo_guard.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_numstat_handles_text_and_binary_rows():
    repo_guard = load_repo_guard()

    entries = repo_guard.parse_numstat("12\t3\tcontrol/main.py\n-\t-\toutput/sample.pdf\n")

    assert entries[0].added == 12
    assert entries[0].deleted == 3
    assert entries[0].path == "control/main.py"
    assert entries[1].is_binary


def test_guard_blocks_large_file_count():
    repo_guard = load_repo_guard()
    paths = [f"docs/file_{index}.md" for index in range(4)]
    entries = [repo_guard.NumstatEntry(1, 0, path) for path in paths]

    errors = repo_guard.evaluate_entries(entries, paths, max_files=3)

    assert any("touches 4 files" in error for error in errors)


def test_guard_blocks_large_text_delta():
    repo_guard = load_repo_guard()
    entries = [repo_guard.NumstatEntry(801, 0, "docs/big.md")]

    errors = repo_guard.evaluate_entries(entries, ["docs/big.md"], max_lines=800)

    assert any("801 added/deleted" in error for error in errors)


def test_guard_blocks_balanced_rewrite_noise():
    repo_guard = load_repo_guard()
    entries = [repo_guard.NumstatEntry(500, 500, "control/gui_panels.py")]

    errors = repo_guard.evaluate_entries(
        entries,
        ["control/gui_panels.py", "tests/test_gui_panels.py"],
        max_balanced_rewrite_lines=500,
    )

    assert any("balanced 500/500 rewrite" in error for error in errors)


def test_guard_requires_tests_for_control_changes():
    repo_guard = load_repo_guard()
    entries = [repo_guard.NumstatEntry(5, 1, "control/main.py")]

    errors = repo_guard.evaluate_entries(entries, ["control/main.py"])

    assert "control/*.py changed without a matching tests/*.py change" in errors


def test_guard_accepts_control_changes_with_tests():
    repo_guard = load_repo_guard()
    entries = [
        repo_guard.NumstatEntry(5, 1, "control/main.py"),
        repo_guard.NumstatEntry(8, 0, "tests/test_main.py"),
    ]

    errors = repo_guard.evaluate_entries(entries, ["control/main.py", "tests/test_main.py"])

    assert errors == []
