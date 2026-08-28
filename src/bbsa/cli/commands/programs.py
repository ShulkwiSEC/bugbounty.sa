"""bbsa programs list / show."""

from __future__ import annotations

import argparse

from bbsa import api
from bbsa.cli.formatters import (
    EXIT_OK,
    bold,
    dim,
    green,
    print_json_success,
    render_kv,
    render_table,
    red,
    suggest_next_step,
    text,
)


def _platform_name(p: dict) -> str:
    plat = p.get("platform")
    if isinstance(plat, dict):
        return str(plat.get("name") or "-")
    return str(plat or "-")


def cmd_programs_list(args: argparse.Namespace) -> int:
    resp = api.get("/programs")
    items = resp.get("data") or []
    meta = resp.get("meta") or {}
    total = meta.get("total") if meta.get("total") is not None else len(items)
    # ponytail: client-side slice; switch to server page/limit if lists grow large
    shown = items[: args.limit] if args.limit else items

    if args.json:
        print_json_success(shown, meta={"total": total, "shown": len(shown)})
        return EXIT_OK
    if not shown:
        print(dim("No programs found."))
        return EXIT_OK

    rows = [
        [
            str(p.get("id", "-")),
            text(p.get("name", "-")),
            str(p.get("type", "-")),
            green("active") if p.get("is_active") else red("inactive"),
            _platform_name(p),
            str(p.get("end_date") or p.get("end") or "-"),
        ]
        for p in shown
    ]
    print(render_table(["ID", "NAME", "TYPE", "STATUS", "PLATFORM", "ENDS"], rows))
    if len(shown) < total:
        suggest_next_step(f"Showing {len(shown)} of {total} — see all with --limit {total}")
    else:
        suggest_next_step("bbsa programs show <ID> for scope, policy, reward ranges")
    return EXIT_OK


def cmd_programs_show(args: argparse.Namespace) -> int:
    prog = api.get(f"/programs/{args.id}")["data"]
    if args.json:
        print_json_success(prog)
        return EXIT_OK

    pairs = [
        ("ID", str(prog.get("id"))),
        ("Name", str(prog.get("name") or "-")),
        ("Type", str(prog.get("type") or "-")),
        ("Platform", _platform_name(prog)),
        ("Status", green("active") if prog.get("is_active") else red("inactive")),
        ("Start", str(prog.get("start_date") or "-")),
        ("End", str(prog.get("end_date") or "-")),
    ]
    print(bold(f"══ Program {prog.get('id')}: {prog.get('name')} ══\n"))
    print(render_kv(pairs))

    ranges = [
        (lvl.title(), f"{prog.get(f'{lvl}_range_from')} - {prog.get(f'{lvl}_range_to')}")
        for lvl in ("critical", "high", "medium", "low")
        if prog.get(f"{lvl}_range_from") is not None
    ]
    if ranges:
        print(f"\n{bold('Reward Ranges:')}")
        print(render_kv(ranges))

    domains = prog.get("domains") or []
    if domains:
        print(f"\n{bold('Domains:')}")
        for d in domains:
            print(f"  • {d.get('domain', d) if isinstance(d, dict) else d}")

    policy = prog.get("policy")
    if policy:
        print(f"\n{bold('Policy:')}\n{policy}")

    out = prog.get("out_of_scope")
    if out:
        print(f"\n{bold('Out of Scope:')}\n{out}")

    print()
    suggest_next_step("bbsa reports list --json | jq '.[] | {id, status}'")
    return EXIT_OK