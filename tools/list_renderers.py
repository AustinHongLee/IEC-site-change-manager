# -*- coding: utf-8 -*-
"""List available output renderer backends."""

from __future__ import annotations

import argparse
import json
import os
import sys


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from console_io import configure_utf8_stdio
from renderer_registry import list_renderers


configure_utf8_stdio()


def main() -> int:
    ap = argparse.ArgumentParser(description="列出可用輸出 renderer")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    ap.add_argument("--probe-com", action="store_true", help="實際啟動 Excel 探測 COM 可用性")
    args = ap.parse_args()

    renderers = list_renderers(probe_com_application=args.probe_com)
    if args.json:
        print(json.dumps({"renderers": renderers}, ensure_ascii=False, indent=2))
        return 0

    for renderer in renderers:
        state = "可用" if renderer.get("available") else "不可用"
        legacy = " / legacy" if renderer.get("legacy") else ""
        print(f"{renderer.get('kind')} - {renderer.get('label')} [{state}{legacy}]")
        print(f"  status: {renderer.get('status')}")
        print(f"  data: {renderer.get('data_contract')}")
        if renderer.get("reason"):
            print(f"  reason: {renderer.get('reason')}")
        if renderer.get("detail"):
            print(f"  detail: {renderer.get('detail')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
