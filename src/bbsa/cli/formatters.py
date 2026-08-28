"""CLI formatters: JSON envelopes, exit codes, ANSI color, tables, hints.

Mirrors the oh-my-ctf CLI conventions: stable JSON with --json, tab-separated
plain text when piped, ANSI color only on a TTY, data on stdout / errors on
stderr, bounded human output with next-step hints.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Sequence
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3

_COLOR_OVERRIDE: bool | None = None


def set_color_enabled(enabled: bool | None) -> None:
    global _COLOR_OVERRIDE
    _COLOR_OVERRIDE = enabled


def is_color_enabled(stream=sys.stdout) -> bool:
    if _COLOR_OVERRIDE is not None:
        return _COLOR_OVERRIDE
    if "NO_COLOR" in os.environ:
        return False
    return hasattr(stream, "isatty") and stream.isatty()


def _ansi(code: str, text: str, stream=sys.stdout) -> str:
    if not is_color_enabled(stream):
        return str(text)
    return f"\033[{code}m{text}\033[0m"


def bold(text, stream=sys.stdout):
    return _ansi("1", text, stream)


def dim(text, stream=sys.stdout):
    return _ansi("2", text, stream)


def red(text, stream=sys.stdout):
    return _ansi("31", text, stream)


def green(text, stream=sys.stdout):
    return _ansi("32", text, stream)


def yellow(text, stream=sys.stdout):
    return _ansi("33", text, stream)


def cyan(text, stream=sys.stdout):
    return _ansi("36", text, stream)


def pick(d: dict, *keys, default: Any = "") -> Any:
    """First present key in d, or default. Immune to unknown response shapes."""
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def text(v: Any, max_len: int = 80) -> str:
    """Human-friendly single-line rendering. Nested dicts collapse to their
    name/label/title; long strings are truncated (bounded output)."""
    if isinstance(v, dict):
        for k in ("name", "label", "title", "title_en", "value"):
            if v.get(k) is not None:
                return text(v[k], max_len)
        return str(v)[:max_len]
    if isinstance(v, bool):
        return str(v)
    s = str(v)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


# ── JSON envelopes ────────────────────────────────────────────────────


def format_json_success(data: Any, meta: dict[str, Any] | None = None) -> str:
    payload = {
        "ok": True,
        "data": data,
        "meta": meta
        or {"side_effects": False, "estimated_cost": None, "retryable": False},
    }
    return json.dumps(payload, indent=2)


def format_json_error(
    code: str, message: str, retryable: bool = False, details: Any = None
) -> str:
    payload = {
        "ok": False,
        "error": {"code": code, "message": message, "retryable": retryable, "details": details},
    }
    return json.dumps(payload, indent=2)


def print_json_success(data: Any, meta: dict[str, Any] | None = None) -> None:
    print(format_json_success(data, meta))


def print_json_error(
    code: str, message: str, retryable: bool = False, details: Any = None
) -> None:
    print(format_json_error(code, message, retryable, details))


# ── Tables & text ─────────────────────────────────────────────────────


def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    alignments: Sequence[str] | None = None,
    stream=sys.stdout,
) -> str:
    """Aligned table on a TTY; tab-separated plain rows when piped."""
    if not rows:
        return ""
    is_tty = is_color_enabled(stream) or (hasattr(stream, "isatty") and stream.isatty())
    align = list(alignments or ["<"] * len(headers))
    while len(align) < len(headers):
        align.append("<")

    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(_strip_ansi(str(val))))

    if not is_tty:
        lines = ["\t".join(str(h) for h in headers)]
        for row in rows:
            lines.append("\t".join(str(cell) for cell in row))
        return "\n".join(lines)

    def cell(text: str, width: int, alignment: str) -> str:
        clean = _strip_ansi(str(text))
        padding = width - len(clean)
        if padding <= 0:
            return str(text)
        return (" " * padding + str(text)) if alignment == ">" else str(text) + " " * padding

    header_line = "  ".join(
        bold(cell(headers[i], col_widths[i], align[i]), stream) for i in range(len(headers))
    )
    separator = "  ".join(dim("─" * col_widths[i], stream) for i in range(len(headers)))
    lines = [header_line, separator]
    for row in rows:
        lines.append(
            "  ".join(cell(str(row[i]) if i < len(row) else "", col_widths[i], align[i]) for i in range(len(headers)))
        )
    return "\n".join(lines)


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def render_kv(pairs: list[tuple[str, str]], stream=sys.stdout) -> str:
    if not pairs:
        return ""
    max_k = max(len(k) for k, _ in pairs)
    return "\n".join(f"{bold(k.ljust(max_k), stream)} : {v}" for k, v in pairs)


def suggest_next_step(hint: str, stream=sys.stdout) -> None:
    """Print a context-aware next-step hint, TTY only."""
    if hasattr(stream, "isatty") and stream.isatty():
        print(f"\n{dim('Next:', stream)} {cyan(hint, stream)}")