"""bbsa reports list / show / stats."""

from __future__ import annotations

import argparse

from bbsa import api
from bbsa.cli.formatters import (
    EXIT_OK,
    bold,
    dim,
    print_json_success,
    render_kv,
    render_table,
    pick,
    suggest_next_step,
    text,
)


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
    r = api.get(f"/reports/{args.id}")["data"]
    if args.json:
        print_json_success(r)
        return EXIT_OK

    pairs = [
        ("Title", text(pick(r, "title", "name", default="-"))),
        ("Status", text(pick(r, "status", default="-"))),
        ("Severity", text(pick(r, "severity", default="-"))),
        ("Program", text(pick(r, "program", default=""))),
        ("Created", text(pick(r, "created_at", default="-"))),
        ("Updated", text(pick(r, "updated_at", default="-"))),
        ("Summary", text(pick(r, "summary", default=""))),
    ]
    pairs = [(k, v) for k, v in pairs if v]
    print(bold(f"══ Report {args.id} ══\n"))
    print(render_kv(pairs))

    desc = pick(r, "description", "body", "reproduction_steps", default="")
    if desc:
        print(f"\n{bold('Description:')}\n{desc}")

    print("\nFull fields available with --json.")
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