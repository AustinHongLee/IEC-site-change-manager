# -*- coding: utf-8 -*-
"""
Small local guardrails for agent-driven changes.

The hook intentionally stays conservative. If a legitimate large change is
needed, run the guard manually with a higher threshold and keep that decision
visible in the commit notes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MAX_FILES = 15
DEFAULT_MAX_LINES = 800
DEFAULT_MAX_BALANCED_REWRITE_LINES = 500


@dataclass(frozen=True)
class NumstatEntry:
    added: int | None
    deleted: int | None
    path: str

    @property
    def is_binary(self) -> bool:
        return self.added is None or self.deleted is None

    @property
    def total_changed_lines(self) -> int:
        if self.is_binary:
            return 0
        return int(self.added or 0) + int(self.deleted or 0)


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def parse_numstat_line(line: str) -> NumstatEntry:
    added_raw, deleted_raw, path = line.rstrip("\n").split("\t", 2)
    if added_raw == "-" or deleted_raw == "-":
        return NumstatEntry(None, None, path)
    return NumstatEntry(int(added_raw), int(deleted_raw), path)


def parse_numstat(output: str) -> list[NumstatEntry]:
    return [parse_numstat_line(line) for line in output.splitlines() if line.strip()]


def is_control_python(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized.startswith("control/") and normalized.endswith(".py")


def is_test_python(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized.startswith("tests/") and normalized.endswith(".py")


def evaluate_entries(
    entries: list[NumstatEntry],
    changed_paths: list[str],
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_lines: int = DEFAULT_MAX_LINES,
    max_balanced_rewrite_lines: int = DEFAULT_MAX_BALANCED_REWRITE_LINES,
    require_tests_for_control: bool = True,
) -> list[str]:
    errors: list[str] = []
    total_lines = sum(entry.total_changed_lines for entry in entries)

    if len(changed_paths) > max_files:
        errors.append(
            f"change touches {len(changed_paths)} files, over the limit of {max_files}; "
            "split the work into smaller commits"
        )

    if total_lines > max_lines:
        errors.append(
            f"change has {total_lines} added/deleted text lines, over the limit of {max_lines}; "
            "split the work or raise the limit explicitly"
        )

    for entry in entries:
        if entry.is_binary:
            continue
        if (
            entry.added == entry.deleted
            and int(entry.added or 0) >= max_balanced_rewrite_lines
        ):
            errors.append(
                f"{entry.path} has a balanced {entry.added}/{entry.deleted} rewrite; "
                "check for line-ending or full-file rewrite noise"
            )

    if require_tests_for_control:
        control_changed = any(is_control_python(path) for path in changed_paths)
        tests_changed = any(is_test_python(path) for path in changed_paths)
        if control_changed and not tests_changed:
            errors.append("control/*.py changed without a matching tests/*.py change")

    return errors


def _git_diff_base_args(staged: bool) -> list[str]:
    args = ["diff"]
    if staged:
        args.append("--cached")
    return args


def run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def collect_changed_paths(cwd: Path, staged: bool) -> list[str]:
    result = run_git(cwd, [*_git_diff_base_args(staged), "--name-only"])
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def collect_numstat(cwd: Path, staged: bool) -> list[NumstatEntry]:
    result = run_git(cwd, [*_git_diff_base_args(staged), "--numstat"])
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip())
    return parse_numstat(result.stdout)


def check_whitespace(cwd: Path, staged: bool) -> tuple[bool, str]:
    result = run_git(cwd, [*_git_diff_base_args(staged), "--check"])
    return result.returncode == 0, result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Guard repo changes before commit")
    parser.add_argument("--staged", action="store_true", help="check staged changes")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument(
        "--max-balanced-rewrite-lines",
        type=int,
        default=DEFAULT_MAX_BALANCED_REWRITE_LINES,
    )
    parser.add_argument(
        "--no-control-test-requirement",
        action="store_true",
        help="do not require tests/*.py when control/*.py changes",
    )
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    try:
        whitespace_ok, whitespace_output = check_whitespace(repo, args.staged)
        changed_paths = collect_changed_paths(repo, args.staged)
        entries = collect_numstat(repo, args.staged)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    if not changed_paths:
        print("repo guard: no staged changes" if args.staged else "repo guard: no changes")
        return 0

    total_lines = sum(entry.total_changed_lines for entry in entries)
    print(f"repo guard: files={len(changed_paths)}, text_lines={total_lines}")

    errors: list[str] = []
    if not whitespace_ok:
        errors.append("git diff --check failed")
        if whitespace_output:
            errors.append(whitespace_output)

    errors.extend(
        evaluate_entries(
            entries,
            changed_paths,
            max_files=args.max_files,
            max_lines=args.max_lines,
            max_balanced_rewrite_lines=args.max_balanced_rewrite_lines,
            require_tests_for_control=not args.no_control_test_requirement,
        )
    )

    if errors:
        print("repo guard failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("repo guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
