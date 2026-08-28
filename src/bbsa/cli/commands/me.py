"""bbsa me — current researcher profile."""

from __future__ import annotations

import argparse

from bbsa import api
from bbsa.cli.formatters import EXIT_OK, bold, print_json_success, render_kv, suggest_next_step


def cmd_me(args: argparse.Namespace) -> int:
    data = api.get("/me")["data"]
    if args.json:
        print_json_success(data)
        return EXIT_OK

    res = data.get("researcher") or {}
    country = data.get("country")
    if isinstance(country, dict):
        country = country.get("name") or country.get("id")
    pairs = [
        ("Name", str(data.get("full_name") or data.get("name") or "-")),
        ("Username", str(data.get("username") or "-")),
        ("Email", str(data.get("email") or "-")),
        ("Country", str(country or "-")),
        ("Verified", str(bool(data.get("is_verified")))),
        ("Rank", str(res.get("rank") or "-")),
        ("Points", str(res.get("points") or 0)),
        ("Total Bounties", str(res.get("total_bounties") or 0)),
        ("Resolved Reports", str(res.get("resolved_reports") or 0)),
        ("Full data", "run with --json"),
    ]
    print(bold("══ Your Profile ══\n"))
    print(render_kv(pairs))
    suggest_next_step("bbsa programs list")
    return EXIT_OK