# -*- coding: utf-8 -*-
"""
Record a compact AI engineering session note under docs/.../ai_sessions.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DOCS_DIR = Path("docs") / "00_big_bang_產品進化總控室"
AI_SESSIONS_DIR = DOCS_DIR / "ai_sessions"


@dataclass(frozen=True)
class GitSnapshot:
    branch_status: str
    head: str
    recent_log: str
    diff_stat: str


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def slugify_topic(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", value.strip())
    slug = re.sub(r"-+", "-", slug).strip("-_")
    return slug or "session"


def today_string(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")


def run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    text = result.stdout.strip()
    if result.returncode != 0:
        return f"<git command failed: git {' '.join(args)}>\n{text}".strip()
    return text


def collect_git_snapshot(repo: Path) -> GitSnapshot:
    return GitSnapshot(
        branch_status=run_git(repo, ["status", "--short", "--branch"]),
        head=run_git(repo, ["rev-parse", "--short", "HEAD"]),
        recent_log=run_git(repo, ["log", "--oneline", "-5"]),
        diff_stat=run_git(repo, ["diff", "--stat"]) or "<no working tree diff>",
    )


def bullet_lines(items: list[str], empty_text: str = "無") -> str:
    clean_items = [item.strip() for item in items if item.strip()]
    if not clean_items:
        return f"- {empty_text}"
    return "\n".join(f"- {item}" for item in clean_items)


def fenced(text: str) -> str:
    return f"```text\n{text.strip() or '<empty>'}\n```"


def build_session_markdown(
    *,
    title: str,
    date: str,
    role: str,
    goal: str,
    snapshot: GitSnapshot,
    summaries: list[str],
    validations: list[str],
    risks: list[str],
    next_steps: list[str],
) -> str:
    return "\n".join([
        f"# {title}",
        "",
        f"日期：{date}",
        f"角色：{role}",
        "",
        "## 本次目標",
        "",
        goal.strip() or "未填寫",
        "",
        "## 主要變更摘要",
        "",
        bullet_lines(summaries),
        "",
        "## 驗證紀錄",
        "",
        bullet_lines(validations),
        "",
        "## 風險與注意事項",
        "",
        bullet_lines(risks),
        "",
        "## 下一步",
        "",
        bullet_lines(next_steps),
        "",
        "## Git Snapshot",
        "",
        "### Branch Status",
        "",
        fenced(snapshot.branch_status),
        "",
        "### HEAD",
        "",
        fenced(snapshot.head),
        "",
        "### Recent Log",
        "",
        fenced(snapshot.recent_log),
        "",
        "### Working Tree Diff Stat",
        "",
        fenced(snapshot.diff_stat),
        "",
    ])


def next_available_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        next_candidate = directory / f"{stem}-{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise RuntimeError(f"cannot find available filename for {filename}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record an AI engineering session")
    parser.add_argument("--topic", required=True, help="short topic used in title and filename")
    parser.add_argument("--goal", required=True, help="what this session tried to accomplish")
    parser.add_argument("--role", default="工程實作", help="session role")
    parser.add_argument("--summary", action="append", default=[], help="change summary bullet")
    parser.add_argument("--validation", action="append", default=[], help="validation bullet")
    parser.add_argument("--risk", action="append", default=[], help="risk or caveat bullet")
    parser.add_argument("--next", dest="next_steps", action="append", default=[], help="next step bullet")
    parser.add_argument("--date", default="", help="override YYYY-MM-DD date")
    parser.add_argument("--dry-run", action="store_true", help="print output path and content without writing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    date = args.date or today_string()
    topic_slug = slugify_topic(args.topic)
    title = f"AI Session：{args.topic}"
    filename = f"{date}_codex_{topic_slug}.md"
    output_dir = repo / AI_SESSIONS_DIR
    output_path = next_available_path(output_dir, filename)

    snapshot = collect_git_snapshot(repo)
    content = build_session_markdown(
        title=title,
        date=date,
        role=args.role,
        goal=args.goal,
        snapshot=snapshot,
        summaries=args.summary,
        validations=args.validation,
        risks=args.risk,
        next_steps=args.next_steps,
    )

    if args.dry_run:
        print(f"Would write: {output_path}")
        print(content)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8", newline="\n")
    print(f"AI session written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
