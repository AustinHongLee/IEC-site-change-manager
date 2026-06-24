# -*- coding: utf-8 -*-
"""Pure weld code parser and allocator for canonical change-order events."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable

from change_order import Origin, WeldEvent


@dataclass(frozen=True)
class WeldScheme:
    new_weld_base: int = 1000
    rework_letters: str = "abcdefghijklmnopqrstuvwxyz"


@dataclass(frozen=True)
class ParsedCode:
    base: str | None
    rework_seq: int
    is_new: bool
    raw: str
    parsed: bool


DEFAULT_SCHEME = WeldScheme()
_CODE_RE = re.compile(r"^(?P<number>\d+)(?P<letter>[A-Za-z]?)$")


def parse(code: str, scheme: WeldScheme = DEFAULT_SCHEME) -> ParsedCode:
    """Parse a field weld code without raising on malformed input."""
    raw = "" if code is None else str(code).strip()
    if not raw:
        return ParsedCode(base=None, rework_seq=0, is_new=False, raw=raw, parsed=False)

    body = raw[1:] if raw.lower().startswith("w") else raw
    match = _CODE_RE.fullmatch(body)
    if match is None:
        return ParsedCode(base=None, rework_seq=0, is_new=False, raw=raw, parsed=False)

    number = _normalize_number(match.group("number"))
    letter = match.group("letter").lower()
    if letter:
        seq = _seq_for_letter(letter, scheme)
        if seq is None:
            return ParsedCode(base=None, rework_seq=0, is_new=False, raw=raw, parsed=False)
        return ParsedCode(base=number, rework_seq=seq, is_new=False, raw=raw, parsed=True)

    is_new = int(number) >= scheme.new_weld_base
    return ParsedCode(
        base=None if is_new else number,
        rework_seq=0,
        is_new=is_new,
        raw=raw,
        parsed=True,
    )


def next_rework(
    base: str,
    existing_ids: list[str],
    scheme: WeldScheme = DEFAULT_SCHEME,
) -> tuple[str, int]:
    """Return the next rework code and sequence for an existing base weld."""
    base_text = _normalize_base(base)
    max_seq = 0
    for existing_id in existing_ids:
        seq = _rework_seq_for_base(existing_id, base_text, scheme)
        if seq is not None:
            max_seq = max(max_seq, seq)

    next_seq = max_seq + 1
    return f"{base_text}{_letter_for_seq(next_seq, scheme)}", next_seq


def next_new(
    existing_ids: list[str],
    scheme: WeldScheme = DEFAULT_SCHEME,
    exists: Callable[[str], bool] | None = None,
) -> str:
    """Return the next safe 1000+ weld code."""
    max_number = scheme.new_weld_base
    for existing_id in existing_ids:
        raw = "" if existing_id is None else str(existing_id).strip()
        if raw.isdigit():
            max_number = max(max_number, int(raw))

    candidate = max_number + 1
    while exists is not None and exists(str(candidate)):
        candidate += 1
    return str(candidate)


def assign_event(
    event: WeldEvent,
    existing_ids: list[str],
    *,
    exists: Callable[[str], bool] | None = None,
    scheme: WeldScheme = DEFAULT_SCHEME,
) -> WeldEvent:
    """Return a copied event with its field weld code assigned."""
    origin = _origin_value(event.origin)
    if origin == Origin.EXISTING.value:
        if event.base is None or str(event.base).strip() == "":
            raise ValueError("existing weld event requires base")
        code, rework_index = next_rework(event.base, existing_ids, scheme)
        return replace(event, code=code, rework_index=rework_index)
    if origin == Origin.NEW.value:
        return replace(event, code=next_new(existing_ids, scheme, exists), rework_index=None)
    raise ValueError(f"unsupported weld event origin: {event.origin!r}")


def _normalize_number(value: str) -> str:
    return value.lstrip("0") or "0"


def _normalize_base(base: str) -> str:
    text = "" if base is None else str(base).strip()
    if text.lower().startswith("w") and text[1:].isdigit():
        return _normalize_number(text[1:])
    if text.isdigit():
        return _normalize_number(text)
    return text


def _seq_for_letter(letter: str, scheme: WeldScheme) -> int | None:
    try:
        return scheme.rework_letters.index(letter) + 1
    except ValueError:
        return None


def _letter_for_seq(seq: int, scheme: WeldScheme) -> str:
    if seq < 1 or seq > len(scheme.rework_letters):
        raise ValueError(f"rework sequence {seq} is outside the configured letter scheme")
    return scheme.rework_letters[seq - 1]


def _rework_seq_for_base(existing_id: str, base: str, scheme: WeldScheme) -> int | None:
    parsed = parse(existing_id, scheme)
    if parsed.parsed and not parsed.is_new and parsed.base == base:
        return parsed.rework_seq

    raw = "" if existing_id is None else str(existing_id).strip()
    if raw == base:
        return 0
    if raw.startswith(base) and len(raw) == len(base) + 1:
        return _seq_for_letter(raw[-1].lower(), scheme)
    return None


def _origin_value(origin) -> str | None:
    return origin.value if hasattr(origin, "value") else origin


__all__ = [
    "ParsedCode",
    "WeldScheme",
    "assign_event",
    "next_new",
    "next_rework",
    "parse",
]
