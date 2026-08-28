# bugbounty.sa (bbsa)

| CLI Mode (`bbsa`) | Agent / MCP Mode (`anthropic(claude)`) |
| :---: | :---: |
| ![bbsa demo](demo.gif) | ![bbsa-mcp demo](claude-demo.gif) |

Read-only CLI + MCP server for [bugbounty.sa](https://bugbounty.sa) — query programs, reports, invoices, the leaderboard, and notifications from your terminal or your agent. Report submission stays strictly manual.

- **CLI:** `bbsa`
- **MCP server:** `bbsa-mcp`
- **Repo:** [github.com/ShulkwiSEC/bugbounty.sa](https://github.com/ShulkwiSEC/bugbounty.sa)

## Features

- **`bbsa` CLI** — agent- and human-friendly: stable `--json` on every command, ANSI color only on a TTY, tab-separated plain output when piped, errors on stderr, exit codes `0`/`1`/`2`/`3`.
- **MCP server** — 14 read-only tools + a `bugbounty://me/profile` resource for Claude, OpenCode, Gemini, etc.
- **Read-only by construction** — every request is `GET`. No mutations exist anywhere in the codebase.
- **One HTTP layer** — the CLI and the MCP server share a single `api.py`; no duplicated request handling, no drift.

## Install

Requires Python 3.12+.

### Native installer (recommended)

The interactive installer installs or updates `uv`, `bbsa`, and `bbsa-mcp` on macOS and Linux. It then lets you select Claude Code, Codex, AGY, OpenCode, or all of them with the arrow keys and Space, and prints the MCP and missing-skill setup to copy and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/install.sh | bash
```

Inspect it before running:

```bash
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/install.sh | less
```

For agents and CI, skip prompts and print setup for every supported agent:

```bash
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/install.sh | bash -s -- --yes
```

### From PyPI

```bash
# run without installing
uvx --refresh-package bugbounty.sa --from bugbounty.sa bbsa
# or install permanently:
uv tool install bugbounty.sa
# or with pip:
pip install bugbounty.sa
```

### From source (dev)

```bash
uv tool install git+https://github.com/ShulkwiSEC/bugbounty.sa
# or, from a clone:
uv pip install -e .
```

## Agent skill (auto-install)

The package ships a [skills.sh](https://skills.sh)-compatible agent skill. The first run of `bbsa` or `bbsa-mcp` silently installs it into every detected coding agent — no user interaction:

| Agent | Skill location |
|---|---|
| Claude Code | `~/.claude/skills/bbsa/` |
| Codex | `~/.codex/skills/bbsa/` |
| AGY | `~/.gemini/antigravity-cli/skills/bbsa/` |
| opencode | `~/.config/opencode/skills/bbsa/` * |

*opencode auto-loads `~/.claude/skills`, so its own folder is skipped while Claude Code is present to avoid duplicates.

The install is idempotent: it skips when the bundled `SKILL.md` already matches, so the CLI stays silent on every run after the first.

### Manual install

To install (or refresh) the skill by hand, copy [`SKILL.md`](https://github.com/ShulkwiSEC/bugbounty.sa/blob/main/src/bbsa/SKILL.md) into the target agent's folder:

```bash
# Claude Code (also covers opencode)
mkdir -p ~/.claude/skills/bbsa
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/src/bbsa/SKILL.md \
  -o ~/.claude/skills/bbsa/SKILL.md

# Codex
mkdir -p ~/.codex/skills/bbsa
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/src/bbsa/SKILL.md \
  -o ~/.codex/skills/bbsa/SKILL.md

# AGY
mkdir -p ~/.gemini/antigravity-cli/skills/bbsa
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/src/bbsa/SKILL.md \
  -o ~/.gemini/antigravity-cli/skills/bbsa/SKILL.md

# opencode (only if you don't use Claude Code)
mkdir -p ~/.config/opencode/skills/bbsa
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/src/bbsa/SKILL.md \
  -o ~/.config/opencode/skills/bbsa/SKILL.md
```

Then restart your agent — skills are loaded at startup.

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

After installing from PyPI (`uv tool install bugbounty.sa` or `pip install bugbounty.sa`), `bbsa-mcp` is on your PATH:

```json
{
  "mcpServers": {
    "bugbounty.sa": {
      "command": "bbsa-mcp",
      "env": { "BUGBOUNTY_SA_TOKEN": "<your-token>" }
    }
  }
}
```

Or run directly without installing:

```json
{
  "mcpServers": {
    "bugbounty.sa": {
      "command": "uvx",
      "args": ["--refresh-package", "bugbounty.sa", "--from", "bugbounty.sa", "bbsa-mcp"],
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
