# -*- coding: utf-8 -*-
"""Generate the compact material catalog rule file.

The UI no longer needs a persisted row for every DN / SCH / material
combination. By default this script writes records/material_catalog_rules.json.
Use --expanded only when a temporary expanded JSON is needed for auditing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL_DIR = ROOT / "control"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from material_catalog_rules import DEFAULT_RULES, all_catalog_rows, catalog_summary, rules_path  # noqa: E402


def write_rules(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULT_RULES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate compact material catalog rules.")
    parser.add_argument("--output", default="", help="Rule JSON output path. Default: records/material_catalog_rules.json")
    parser.add_argument("--expanded", default="", help="Optional expanded audit JSON path. Does not replace the rule source.")
    args = parser.parse_args()

    out = Path(args.output) if args.output else rules_path(ROOT)
    if not out.is_absolute():
        out = ROOT / out
    write_rules(out)

    summary = catalog_summary(ROOT)
    print(f"rules: {out}")
    print(f"virtual rows: {summary['total']}")

    if args.expanded:
        expanded = Path(args.expanded)
        if not expanded.is_absolute():
            expanded = ROOT / expanded
        expanded.parent.mkdir(parents=True, exist_ok=True)
        expanded.write_text(
            json.dumps({"items": all_catalog_rows(ROOT), "meta": {"source": str(out), "kind": "expanded-audit"}},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"expanded audit: {expanded}")


if __name__ == "__main__":
    main()
