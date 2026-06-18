# -*- coding: utf-8 -*-
"""
list_canonical_fields.py - 列出 CanonicalReport 模板可引用欄位

模板作者與 AI 只能引用這份 field-path catalog 內的路徑。
"""

from __future__ import annotations

import os
import sys


_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
_CONTROL_DIR = os.path.join(_ROOT, "control")
if _CONTROL_DIR not in sys.path:
    sys.path.insert(0, _CONTROL_DIR)

from console_io import configure_utf8_stdio
from canonical_fields import list_field_paths


configure_utf8_stdio()


def main() -> int:
    for field in list_field_paths():
        print(field)
    return 0


if __name__ == "__main__":
    sys.exit(main())
