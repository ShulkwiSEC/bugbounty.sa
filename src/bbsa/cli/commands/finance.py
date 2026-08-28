"""bbsa finance — invoices and payout stats."""

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


def cmd_finance_invoices(args: argparse.Namespace) -> int:
    resp = api.get("/invoices")
    items = resp.get("data") or []
    meta = resp.get("meta") or {}
    total = meta.get("total") if meta.get("total") is not None else len(items)
    shown = items[: args.limit] if args.limit else items

    if args.json:
        print_json_success(shown, meta={"total": total, "shown": len(shown)})
        return EXIT_OK
    if not shown:
        print(dim("No invoices found."))
        return EXIT_OK

    rows = [
        [
            str(i.get("id", "-")),
            text(pick(i, "amount", "total", "price", default="-")),
            text(pick(i, "status", "state", default="-")),
            str(pick(i, "created_at", "date", "paid_at", default="-")),
        ]
        for i in shown
    ]
    print(render_table(["ID", "AMOUNT", "STATUS", "DATE"], rows))
    if len(shown) < total:
        suggest_next_step(f"Showing {len(shown)} of {total} invoices — --limit {total} to list all")
    else:
        suggest_next_step("bbsa finance stats")
    return EXIT_OK


def cmd_finance_stats(args: argparse.Namespace) -> int:
    stats = api.get("/invoices/stats")
    if args.json:
        print_json_success(stats)
        return EXIT_OK
    pairs = []
    for k, v in stats.items():
        label = str(k).replace("_", " ").title()
        if isinstance(v, dict):
            v = f"{v.get('count', 0)} invoices, total amount {v.get('amount', 0)}"
        pairs.append((label, str(v)))
    print(bold("══ Invoice Stats ══\n"))
    print(render_kv(pairs))
    suggest_next_step("bbsa finance invoices")
    return EXIT_OK