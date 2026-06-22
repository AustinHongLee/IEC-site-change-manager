# -*- coding: utf-8 -*-
"""
Install this repository's versioned git hooks for the current checkout.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_utf8()
    repo = Path(__file__).resolve().parents[1]
    hooks_dir = repo / ".githooks"
    pre_commit = hooks_dir / "pre-commit"

    if not pre_commit.exists():
        print(f"ERROR: missing hook file: {pre_commit}")
        return 1

    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=repo,
        check=True,
    )
    current = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=repo,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
    ).stdout.strip()

    print(f"Git hooks enabled: core.hooksPath={current}")
    print("Pre-commit guard: python tools/repo_guard.py --staged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
