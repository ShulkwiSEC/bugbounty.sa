"""bbsa leaderboard / notifications — misc queries."""

from __future__ import annotations

import argparse

from bbsa import api
from bbsa.cli.formatters import (
    EXIT_OK,
    bold,
    dim,
    green,
    print_json_success,
    render_table,
    suggest_next_step,
    yellow,
)


def cmd_leaderboard(args: argparse.Namespace) -> int:
    resp = api.get("/leaderboard")
    items = resp.get("items") or []
    if args.json:
        print_json_success(items, meta={"total": len(items)})
        return EXIT_OK
    if not items:
        print(dim("Leaderboard is empty."))
        return EXIT_OK
    rows = [
        [
            f"#{i.get('rank')}",
            str(i.get("username", "-")),
            str(i.get("company_researcher_points") or i.get("points") or 0),
            green("verified") if i.get("is_verified") else "not verified",
        ]
        for i in items
    ]
    print(bold("══ Top Researchers ══\n"))
    print(render_table(["RANK", "USERNAME", "POINTS", "VERIFIED"], rows))
    suggest_next_step(r"jq filter: bbsa leaderboard --json | jq -r '.data[] | \"\(.rank) \(.username)\"'")
    return EXIT_OK


def cmd_notifications(args: argparse.Namespace) -> int:
    resp = api.get("/notifications")
    items = resp.get("data") or []
    meta = resp.get("meta") or {}
    total = meta.get("total") if meta.get("total") is not None else len(items)
    shown = items[: args.limit] if args.limit else items

    if args.json:
        print_json_success(shown, meta={"total": total, "shown": len(shown)})
        return EXIT_OK
    if not shown:
        print(dim("No notifications."))
        return EXIT_OK

    rows = []
    for n in shown:
        d = n.get("data")
        d = d if isinstance(d, dict) else {}
        title = d.get("title") if isinstance(d.get("title"), dict) else {}
        message = d.get("message")
        if isinstance(message, dict):
            message = message.get("message_en") or str(message)
        text = str(title.get("title_en") or message or "-")
        rows.append([
            str(n.get("id", "-")),
            text,
            green("read") if n.get("read_at") else yellow("unread"),
            str(n.get("created_at", "-")),
        ])
    print(render_table(["ID", "MESSAGE", "STATUS", "AT"], rows))
    if len(shown) < total:
        suggest_next_step(f"Showing {len(shown)} of {total} — --limit {total} for all")
    else:
        suggest_next_step("bbsa reports list")
    return EXIT_OK