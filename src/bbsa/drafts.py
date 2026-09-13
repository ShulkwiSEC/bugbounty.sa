"""Local report drafts — the review gate in front of submission.

A draft is one Markdown file on disk: `key: value` frontmatter for the report's
metadata, then the `# Title` / `## Section` body that `submit.py` already
parses. Files are plain text on purpose — reviewing a draft is opening it in an
editor, and editing one needs no command at all.

Drafts exist so nothing reaches bugbounty.sa unreviewed: every report is drafted
first, and pushing is a separate step the user asks for. Reports cannot be edited
or deleted once submitted (the platform gates `editReport` to admins and triagers,
not researchers), so the only chance to catch a bad report is before it is sent.
The MCP server can write drafts and has no way to push them.

Location: ``$BBSA_DRAFT_DIR``, else ``$XDG_DATA_HOME/bbsa/drafts``, else
``~/.local/share/bbsa/drafts``. Pushed drafts move to a ``pushed/`` subfolder
rather than being deleted.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

__all__ = [
    "META_KEYS",
    "draft_dir",
    "is_draft_id",
    "parse",
    "save",
    "load",
    "load_all",
    "archive",
]

# Frontmatter keys, in the order they are written back out.
META_KEYS = ("program", "domain", "endpoint", "type", "parameter", "attachments")

_ID = re.compile(r"^d(\d+)$")
_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)\Z", re.S)


def draft_dir() -> Path:
    override = os.environ.get("BBSA_DRAFT_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or "~/.local/share"
    return Path(base).expanduser() / "bbsa" / "drafts"


def is_draft_id(value: str) -> bool:
    return bool(_ID.fullmatch(str(value).strip()))


def _path(draft_id: str) -> Path:
    return draft_dir() / f"{draft_id}.md"


def _next_id() -> str:
    # rglob, not glob: ids must not be reused after every pending draft is pushed,
    # or the next push would overwrite an archived report's only local copy.
    used = {
        int(m.group(1))
        for f in draft_dir().rglob("d*.md")
        if (m := _ID.fullmatch(f.stem))
    }
    return f"d{max(used, default=0) + 1}"


def parse(raw: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER.match(raw)
    if not match:
        return {}, raw.strip()
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, match.group(2).strip()


def _render(meta: dict[str, str], body: str) -> str:
    ordered = [(k, meta[k]) for k in META_KEYS if str(meta.get(k, "")).strip()]
    ordered += [(k, v) for k, v in meta.items() if k not in META_KEYS and str(v).strip()]
    front = "\n".join(f"{k}: {v}" for k, v in ordered)
    return f"---\n{front}\n---\n\n{body.strip()}\n"


def save(meta: dict, body: str, draft_id: str | None = None) -> tuple[str, Path]:
    """Write a draft, allocating the next free id when one is not given."""
    directory = draft_dir()
    directory.mkdir(parents=True, exist_ok=True)
    draft_id = draft_id or _next_id()
    path = _path(draft_id)
    path.write_text(_render({k: str(v) for k, v in meta.items()}, body), encoding="utf-8")
    return draft_id, path


def load(draft_id: str) -> tuple[dict[str, str], str, Path]:
    path = _path(draft_id)
    if not path.is_file():
        raise FileNotFoundError(f"No draft {draft_id} in {draft_dir()}")
    meta, body = parse(path.read_text(encoding="utf-8"))
    return meta, body, path


def load_all() -> list[tuple[str, dict[str, str], str, Path]]:
    """Every pending draft, newest first. Pushed drafts live in pushed/ and are
    not returned — they are real reports now, so the API is their source."""
    found = []
    for path in draft_dir().glob("d*.md"):
        if not _ID.fullmatch(path.stem):
            continue
        meta, body = parse(path.read_text(encoding="utf-8"))
        found.append((path.stem, meta, body, path))
    return sorted(found, key=lambda item: item[3].stat().st_mtime, reverse=True)


def archive(draft_id: str, report: dict | None = None) -> Path:
    """Move a pushed draft aside. Kept, not deleted — it is the only local copy
    of a report the platform will not let a researcher edit."""
    meta, body, path = load(draft_id)
    if report:
        meta = {**meta, "pushed_as": str(report.get("slug") or report.get("id") or "")}
    destination = draft_dir() / "pushed" / path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_render(meta, body), encoding="utf-8")
    path.unlink()
    return destination
