---
name: bbsa
description: Read-only CLI and MCP server for the bugbounty.sa bug bounty platform (PyPI package bugbounty.sa; executables bbsa and bbsa-mcp). This skill should be used when the user asks to read data from bugbounty.sa — their researcher profile, bug bounty programs, reports, invoices, finance, transactions, leaderboard, companies, or notifications — or needs help setting up or troubleshooting the bbsa token and MCP server. Triggers on "bbsa", "bugbounty.sa", "check my reports", "list programs", "my leaderboard", "bug bounty platform", "bugbounty.sa MCP". Provides exact CLI commands, MCP tool mappings, and JSON output patterns.
license: Apache-2.0
---

# bbsa — bugbounty.sa CLI + MCP

bbsa is a read-only CLI (`bbsa`) and MCP server (`bbsa-mcp`) for bugbounty.sa. Every request is a `GET`; there are no write endpoints anywhere. Report submission stays strictly manual.

## When to use

Use when the user wants data from bugbounty.sa: profile, programs, reports, invoices, finance, leaderboard, companies, or notifications, or needs the token/MCP setup.

**Not for**: submitting, editing, or deleting platform data. Out of scope by design — say so if asked.

## Preferred interface (default first)

1. **MCP tools** — if connected to `bbsa-mcp`, call the tools directly; no shell needed.
2. **CLI** — otherwise shell out to `bbsa`. Use `--json` when reasoning over results; plain output is for humans.

If `bbsa` is not on PATH, run the latest release without installing: `uvx --refresh-package bugbounty.sa --from bugbounty.sa bbsa`.

For a user-authorized install or update of the CLI, MCP server, and agent skill:

```bash
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/install.sh | bash -s -- --yes
```

## Auth

```bash
export BUGBOUNTY_SA_TOKEN="your-token"
```

Public endpoints (leaderboard, program list, companies) work without a token. Private endpoints return `401` with a message naming the variable to set. Never echo or write the token to output, logs, or files.

## Core procedures (CLI)

Profile:
```bash
bbsa me
```

Programs (public):
```bash
bbsa programs list                    # columns: ID NAME TYPE STATUS PLATFORM ENDS
bbsa programs show <ID>               # scope, policy, reward ranges, domains
bbsa programs show <ID> --json | jq .data.domains
```

Reports (private):
```bash
bbsa reports list                     # includes the numeric report ID
bbsa reports show <ID-or-slug>        # full report + comments; accepts either
bbsa reports stats [--group]          # counts by status | severity | type
```

Finance (private):
```bash
bbsa finance invoices
bbsa finance stats                    # paid / unpaid totals
```

Leaderboard (public):
```bash
bbsa leaderboard                      # top 10 researchers
```

Notifications (private):
```bash
bbsa notifications
```

## Reasoning with JSON

Every command accepts `--json` and emits a `data` key. Examples:

```bash
bbsa leaderboard --json | jq -r '.data[] | "\(.rank) \(.username)"'
bbsa reports list --json | jq -c '.data[] | select(.severity == "high")'
```

## MCP tools

`list_programs`, `get_program_scope`, `list_reports`, `get_report`, `get_report_stats`, `get_wallet_balance`, `list_invoices`, `get_invoice_stats`, `list_transactions`, `get_transaction_stats`, `get_public_leaderboard`, `list_companies`, `get_company`, `list_notifications`. Resource: `bugbounty://me/profile`.

- `list_reports` returns each report's numeric `id` and slug.
- `get_report(report_id_or_slug)` accepts either value and includes follow-up comments in `data.comments`.

## Gotchas

- **Every command** needs `--json` flag; the flag is not a global option that flips the whole subcommand tree.
- Exit codes are meaningful: `0` ok, `1` error, `2` usage, `3` not found. Check the code before blaming the network.
- ANSI color appears only on a TTY; piped output is tab-separated plain. Use `--no-color` in scripts.
- Never invent report IDs — get the numeric `id` from `reports list`/`list_reports`, then pass it to `reports show`/`get_report`.
- Program end dates and leaderboard positions change over time. Never assert a program's status or a rank from memory.
- Private endpoints fail with `401` when `BUGBOUNTY_SA_TOKEN` is unset — that is the first thing to check.

## Workflows

1. **Investigate open work** — `reports list`, then `reports show` for any still in triage; summarize status, severity, and next step per report.
2. **Recon a program** — `programs list`, then `programs show` the highest-bounty public program; report scope, reward ranges, and domains.
3. **Researcher briefing** — `leaderboard`, `notifications`, and `me`; compare the user's profile to the leaders.

## Guardrails

- Read-only. Never attempt submits, edits, or deletes — the API has no such endpoints.
- Never expose `BUGBOUNTY_SA_TOKEN` in output, logs, or files.
