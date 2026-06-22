# -*- coding: utf-8 -*-
"""Resolve project data paths separately from bundled application resources."""

from __future__ import annotations

import os
import sys


def resolve_project_dir() -> str:
    """Return the folder that stores project data."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(os.path.dirname(sys.executable))

    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.abspath(os.path.join(here, os.pardir)),
        os.path.abspath(os.path.join(here, os.pardir, os.pardir)),
        here,
    ]
    for base in candidates:
        if os.path.isdir(os.path.join(base, "attachments")) and os.path.isdir(os.path.join(base, "template")):
            return base
    return os.path.abspath(os.path.join(here, os.pardir))


def resolve_resource_dir() -> str:
    """Return the read-only application resource root."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def project_path(*parts: str) -> str:
    return os.path.join(resolve_project_dir(), *parts)


def resource_path(*parts: str) -> str:
    return os.path.join(resolve_resource_dir(), *parts)
