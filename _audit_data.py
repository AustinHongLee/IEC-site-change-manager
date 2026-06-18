# -*- coding: utf-8 -*-
"""資料完整性掃描腳本（保留舊入口，核心邏輯在 control/integrity_audit.py）。"""

import os
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
CONTROL_DIR = os.path.join(ROOT, "control")
if CONTROL_DIR not in sys.path:
    sys.path.insert(0, CONTROL_DIR)

for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    try:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from integrity_audit import audit_integrity, format_integrity_report


if __name__ == "__main__":
    report = audit_integrity(ROOT)
    print(format_integrity_report(report))
    raise SystemExit(1 if report.has_errors else 0)
