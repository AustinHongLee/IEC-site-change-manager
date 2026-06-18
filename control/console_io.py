# -*- coding: utf-8 -*-
"""Small console helpers for Windows CLI entrypoints."""

from __future__ import annotations

import sys
from typing import TextIO


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        _configure_stream(stream)


def _configure_stream(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pass
