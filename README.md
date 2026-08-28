# bugbounty.sa (bbsa)

Read-only CLI + MCP server for [bugbounty.sa](https://bugbounty.sa) — query programs, reports, invoices, the leaderboard, and notifications from your terminal or your agent. Report submission stays strictly manual.

- **CLI:** `bbsa`
- **MCP server:** `bugbounty-sa-mcp`
- **Repo:** [github.com/ShulkwiSEC/bugbounty.sa](https://github.com/ShulkwiSEC/bugbounty.sa)

## Demo

![bbsa demo](demo.gif)

## Features

- **`bbsa` CLI** — agent- and human-friendly: stable `--json` on every command, ANSI color only on a TTY, tab-separated plain output when piped, errors on stderr, exit codes `0`/`1`/`2`/`3`.
- **MCP server** — 14 read-only tools + a `bugbounty://me/profile` resource for Claude, OpenCode, Gemini, etc.
- **Read-only by construction** — every request is `GET`. No mutations exist anywhere in the codebase.
- **One HTTP layer** — the CLI and the MCP server share a single `api.py`; no duplicated request handling, no drift.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/ShulkwiSEC/bugbounty.sa
# or, from a clone:
uv pip install -e .
```

Dependencies: [`httpx`](https://www.python-httpx.org/) (HTTP), [`mcp`](https://github.com/modelcontextprotocol/python-sdk) (MCP server). Build backend: [`uv_build`](https://docs.astral.sh/uv/concepts/build-backend/). The distribution is published on PyPI as `bugbounty.sa`; the import package is `bbsa`.

## Setup

```bash
export BUGBOUNTY_SA_TOKEN="your-bugbounty-sa-token"
```

The token is your bugbounty.sa API token. Without it, private endpoints return a clear `401` telling you exactly what to set.

## Usage

### Quick tour

```
bbsa me                        your researcher profile
bbsa programs list             active programs
bbsa programs show <ID>        scope, policy, reward ranges, domains
bbsa reports list              your reports
bbsa reports show <ID-or-slug> one report's detail
bbsa reports stats [--group]   counts by status|severity|type
bbsa finance invoices          your invoices
bbsa finance stats             invoice totals (paid / unpaid)
bbsa leaderboard               top 10 researchers (public)
bbsa notifications             your notifications
```

### Examples

```console
$ bbsa programs list
ID    NAME              TYPE    STATUS  PLATFORM  ENDS
1475  CoderHub          public  active  Web       2027-08-31T21:00:00.000000Z
1474  Tuwaiq Academy    public  active  Web       2027-08-30T21:00:00.000000Z
313   Flagyard Platform public  active  Web       2026-12-31T03:00:05.000000Z

Next: bbsa programs show <ID> for scope, policy, reward ranges
```

Every command produces stable JSON with `--json`, so it drops straight into pipelines:

```bash
bbsa leaderboard --json | jq -r '.data[] | "\(.rank) \(.username)"'
bbsa reports list --json | jq -c '.data[] | select(.severity == "high")'
bbsa programs show 1475 --json | jq .data.domains
```

Exit codes: `0` ok, `1` error, `2` usage, `3` not found. `--debug` prints full tracebacks; `--no-color` forces plain output for scripting.

### MCP server

```json
{
  "mcpServers": {
    "bugbounty.sa": {
      "command": "bugbounty-sa-mcp",
      "env": { "BUGBOUNTY_SA_TOKEN": "<your-token>" }
    }
  }
}
```

Or via `uv run`:

```json
{
  "mcpServers": {
    "bugbounty.sa": {
      "command": "uv",
      "args": ["run", "bugbounty-sa-mcp"],
      "cwd": "/path/to/repo",
      "env": { "BUGBOUNTY_SA_TOKEN": "<your-token>" }
    }
  }
}
```

Tools: `list_programs`, `get_program_scope`, `list_reports`, `get_report`, `get_report_stats`, `get_wallet_balance`, `list_invoices`, `get_invoice_stats`, `list_transactions`, `get_transaction_stats`, `get_public_leaderboard`, `list_companies`, `get_company`, `list_notifications`. Resource: `bugbounty://me/profile` (`GET /me`).

## Example

Agent prompts that work with the MCP server connected to your client (the agent calls the tools itself — no CLI needed):

1. **Investigate your open work**
   > "List my reports, then for any still in triage pull the full detail and summarize the status, severity, and next step I should take for each."

2. **Recon a program before hunting**
   > "Show me the active programs, then for the highest-bounty public one give me its full scope, reward ranges, and target domains."

3. **Market-scan as a researcher**
   > "Write a short briefing: who's leading the researcher leaderboard, which recent notifications or new programs are relevant to me, and how my profile compares."

## Contributing

Issues and PRs welcome at [github.com/ShulkwiSEC/bugbounty.sa/issues](https://github.com/ShulkwiSEC/bugbounty.sa/issues). Keep it read-only: no write endpoints, no new dependencies without a good reason.

## License

[Apache-2.0](LICENSE) — full text in [`LICENSE`](LICENSE).