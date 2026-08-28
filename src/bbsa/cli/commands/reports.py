"""bbsa reports list / show / stats."""

from __future__ import annotations

import argparse
import html
import re

from bbsa import api
from bbsa.cli.formatters import (
    EXIT_OK,
    bold,
    dim,
    print_json_success,
    render_kv,
    render_table,
    is_color_enabled,
    pick,
    suggest_next_step,
    text,
)
from rich.console import Console
from rich.markdown import Markdown


def _markdown(value: object) -> str:
    """Remove the API's HTML wrappers while preserving embedded Markdown."""
    value = re.sub(r"<(?:br|/p|/div|/li)\b[^>]*>", "\n\n", str(value), flags=re.I)
    value = re.sub(r"<li\b[^>]*>", "- ", value, flags=re.I)
    value = html.unescape(re.sub(r"<[^>]+>", "", value))
    value = re.sub(r"(?m)^[ \N{NO-BREAK SPACE}]*(?=```)", "", value)
    parts = re.split(r"(```.*?```|`[^`\n]*`)", value, flags=re.S)
    return "".join(
        part if i % 2 else part.replace("<", r"\<").replace(">", r"\>")
        for i, part in enumerate(parts)
    ).strip()


def cmd_reports_list(args: argparse.Namespace) -> int:
    resp = api.get("/reports")
    items = resp.get("data") or []
    meta = resp.get("meta") or {}
    total = meta.get("total") if meta.get("total") is not None else len(items)
    # ponytail: client-side slice; switch to server page/limit if get large
    shown = items[: args.limit] if args.limit else items

    if args.json:
        print_json_success(shown, meta={"total": total, "shown": len(shown)})
        return EXIT_OK
    if not shown:
        print(dim("No reports found."))
        return EXIT_OK

    rows = [
        [
            str(r.get("id", "-")),
            text(pick(r, "title", "name", default="-")),
            text(pick(r, "status", default="-")),
            text(pick(r, "severity", default="-")),
            str(pick(r, "created_at", "updated_at", default="-")),
        ]
        for r in shown
    ]
    print(render_table(["ID", "TITLE", "STATUS", "SEVERITY", "UPDATED"], rows))
    if len(shown) < total:
        suggest_next_step(f"Showing {len(shown)} of {total} — see all with --limit {total}")
    else:
        suggest_next_step("bbsa reports show <ID-or-slug> for detail")
    return EXIT_OK


def cmd_reports_show(args: argparse.Namespace) -> int:
    r = api.get_report(args.id)["data"]
    comments = r.pop("comments", [])
    if args.json:
        print_json_success({**r, "comments": comments})
        return EXIT_OK

    fields = [
        ("ID", r.get("id")),
        ("Status", text(r.get("status", "-"))),
        ("Severity", r.get("severity")),
        ("Program", text(r.get("program", ""))),
        ("Type", r.get("type")),
        ("Domain", r.get("domain")),
        ("Endpoint", r.get("endpoint")),
        ("Parameter", r.get("parameter")),
        ("Created", r.get("created_at")),
        ("Updated", r.get("updated_at")),
    ]
    lines = [f"# {_markdown(pick(r, 'title', 'name', default=f'Report {args.id}'))}"]
    lines.extend(f"- **{key}:** {_markdown(value)}" for key, value in fields if value)

    for heading, keys in (
        ("Summary", ("summary",)),
        ("Description", ("description", "body")),
        ("Proof of Concept", ("poc", "reproduction_steps")),
        ("Impact", ("impact",)),
        ("Remediation", ("remediation",)),
    ):
        content = pick(r, *keys, default="")
        if content:
            lines.extend((f"\n## {heading}\n", _markdown(content)))

    lines.append("\n## Comments")
    if not comments:
        lines.append("\n_No comments._")
    for comment in comments:
        author = comment.get("from_user") or {}
        name = author.get("username") or author.get("first_name") or author.get("type") or "Unknown"
        lines.extend(
            (
                f"\n### {_markdown(name)} · {_markdown(comment.get('created_at', ''))}\n",
                _markdown(comment.get("content", "")) or "_Empty comment._",
            )
        )

    Console(no_color=not is_color_enabled()).print(Markdown("\n".join(lines)))
    return EXIT_OK


def cmd_reports_stats(args: argparse.Namespace) -> int:
    resp = api.get("/reports/stats/grouped", {"groupBy": args.group})
    payload = resp.get("data", resp)
    if args.json:
        print_json_success(payload, meta={"group_by": args.group})
        return EXIT_OK

    if isinstance(payload, dict):
        print(bold(f"══ Report Stats (by {args.group}) ══\n"))
        print(render_kv([(str(k), str(v)) for k, v in payload.items()]))
    elif isinstance(payload, list):
        rows = []
        for x in payload:
            if isinstance(x, dict):
                rows.append([str(pick(x, "group", args.group, default="-")), str(x.get("count", "-"))])
            else:
                rows.append([str(x), "?"])
        print(render_table([args.group.title(), "COUNT"], rows))
    else:
        print(str(payload))
    suggest_next_step(r"jq filter: bbsa reports stats --json | jq '.data'")
    return EXIT_OK
