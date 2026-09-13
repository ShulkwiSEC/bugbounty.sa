# bugbounty.sa (bbsa)

| CLI Mode (`bbsa`) | Agent / MCP Mode (`anthropic(claude)`) |
| :---: | :---: |
| ![bbsa demo](demo.gif) | ![bbsa-mcp demo](claude-demo.gif) |

CLI + MCP server for [bugbounty.sa](https://bugbounty.sa) — query programs, reports, invoices, the leaderboard, and notifications, and draft and submit reports, from your terminal or your agent.

- **CLI:** `bbsa`
- **MCP server:** `bbsa-mcp`
- **Repo:** [github.com/ShulkwiSEC/bugbounty.sa](https://github.com/ShulkwiSEC/bugbounty.sa)

## Features

- **`bbsa` CLI** — agent- and human-friendly: stable `--json` on every command, ANSI color only on a TTY, tab-separated plain output when piped, errors on stderr, exit codes `0`/`1`/`2`/`3`.
- **MCP server** — 16 tools + a `bugbounty://me/profile` resource for Claude, OpenCode, Gemini, etc.
- **Draft locally, push deliberately** — `bbsa reports draft` saves a reviewable Markdown file; `bbsa reports push` is the only thing that sends. Drafts appear in `reports list` tagged `draft` alongside your live reports.
- **Pushing is off by default** — `bbsa reports push` refuses to send unless `BBSA_ALLOW_PUSH=1` is set, so an accidental push fails instead of filing an unretractable report. Drafting is never gated.
- **Agents draft, humans decide** — the MCP server has no submit tool at all, so nothing an agent does through MCP can reach the platform.
- **Markdown in, rich text out** — bugbounty.sa's report fields are rich text, not Markdown, so bbsa converts to the HTML the platform actually stores.
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
bbsa reports types [--search]  vulnerability types accepted by --type
bbsa reports draft <file.md>   save a report locally for review (sends nothing)
bbsa reports push <draft-id>   submit a reviewed draft (the only send)
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

Exit codes: `0` ok, `1` error, `2` usage, `3` not found. `reports list` still prints your local drafts when bugbounty.sa is unreachable, but exits `1` and puts the failure in `meta.remote_error` — a failed fetch never reads as an empty account. `--debug` prints full tracebacks; `--no-color` forces plain output for scripting.

### Drafting and submitting a report

Submission is two steps on purpose. **A submitted report cannot be edited or withdrawn** — the platform gates `editReport` to admins and triagers, not researchers — so the draft is your only chance to catch a mistake.

Write the report as one Markdown file. The `# ` heading is the title; the body comes from four `## ` sections — the same layout `bbsa reports show` prints, so an existing report round-trips.

```markdown
# Reflected XSS in the search endpoint

## Summary
The `q` parameter is reflected **without encoding**.

## Proof of Concept
1. Log in as any user.
2. Request `/api/v1/users?q=<svg/onload=alert(1)>`.

## Impact
Session theft and actions performed as the victim.

## Remediation
- Context-encode `q` on output.
```

```bash
bbsa reports types --search xss     # exact --type values live here

bbsa reports draft --program 1475 \
  --domain https://example.com --endpoint /api/v1/users \
  --type 'Reflected - Non-Self' --parameter q report.md
# → Draft d1 saved — nothing has been sent.

bbsa reports show d1                # review it; reports whether it is ready to push
bbsa reports push d1 --dry-run      # the exact payload, still nothing sent

BBSA_ALLOW_PUSH=1 bbsa reports push d1 --agree   # this one sends
```

**Pushing fails closed.** `bbsa reports push` sends nothing unless `BBSA_ALLOW_PUSH=1` is in the environment; without it you get `push_disabled` and the draft is untouched. Pass it inline on the one command you mean to submit rather than exporting it in your shell profile — the point is that submitting is a deliberate act, since it cannot be undone. Drafting, reviewing and `--dry-run` all work without it.

This is a safety catch, not a security boundary: anything that can run the CLI can also set the variable. What it buys you is that no single stray command files a report, and a real submission is greppable in your shell history.

Drafts are plain Markdown files with `key: value` frontmatter, in `$XDG_DATA_HOME/bbsa/drafts` (override with `BBSA_DRAFT_DIR`). Reviewing a draft is opening it in your editor; editing one needs no command. They show up in `bbsa reports list` tagged `draft`, and `reports list` still works when the API is unreachable so long as you have local drafts.

`--agree` is required and stands for the three terms the web form makes you tick — `push --dry-run` prints them. bbsa will not tick them for you. On a successful push the draft moves to `drafts/pushed/` with the live slug recorded rather than being deleted; draft ids are never reused, so an archived report is never overwritten.

**Why Markdown is converted:** bugbounty.sa edits reports in a Quill rich-text editor and stores HTML, so a raw Markdown body renders as literal `**asterisks**` on the platform. bbsa converts to the exact tag set that editor's toolbar produces — `h3`/`h4` (every Markdown heading level folds into those two), `strong`, `em`, `s`, `code`, fenced code blocks, blockquotes, ordered and bullet lists, and links — so a pushed report stays editable in the web UI. Nested lists flatten to one level and horizontal rules are dropped. Add the PoC and evidence with repeatable `--attach PATH` flags when drafting; files upload only during the operator-gated push.

Validation happens locally before anything is sent: `--domain` needs a scheme (`https://example.com`) or a bare IPv4, `--endpoint` must be a path, `--parameter` is `[A-Za-z0-9_-]` only, `--type` must match `bbsa reports types` exactly (near misses get suggestions), and each rendered section must stay under the platform's 5000-character limit.

### Testing the send path without sending

`BBSA_API_URL` repoints the client at a local mock server, so the real HTTP request can be exercised without touching bugbounty.sa — that is what `tests/test_submit_wire.py` does, asserting the exact method, path, headers and JSON body. Only ever point it at a host you control: the bearer token goes wherever it resolves.

```bash
PYTHONPATH=tests python -m unittest test_drafts test_submit test_submit_wire
```

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

Tools: `list_programs`, `get_program_scope`, `list_reports`, `get_report`, `get_report_stats`, `list_vulnerability_types`, `list_submission_agreements`, `list_drafts`, `draft_report`, `get_wallet_balance`, `list_invoices`, `get_invoice_stats`, `list_transactions`, `get_transaction_stats`, `get_public_leaderboard`, `list_companies`, `get_company`, `list_notifications`. Resource: `bugbounty://me/profile` (`GET /me`).

## Example

Agent prompts that work with the MCP server connected to your client (the agent calls the tools itself — no CLI needed):

1. **Investigate your open work**
   > "List my reports, then for any still in triage pull the full detail and summarize the status, severity, and next step I should take for each."

2. **Recon a program before hunting**
   > "Show me the active programs, then for the highest-bounty public one give me its full scope, reward ranges, and target domains."

3. **Market-scan as a researcher**
   > "Write a short briefing: who's leading the researcher leaderboard, which recent notifications or new programs are relevant to me, and how my profile compares."

4. **Draft a finding for review**
   > "Here are my notes on an IDOR in CoderHub's /api/v1/users endpoint. Check it's in scope, pick the right vulnerability type, and save it as a draft for me to review."

   The agent writes the draft and stops — `draft_report` is the only writing tool it has, and it writes to your disk, not to bugbounty.sa. You review with `bbsa reports show d1`, then either push it yourself or tell the agent to. The shipped skill instructs agents to always draft first, never push unless you ask, and never persist `BBSA_ALLOW_PUSH`.

## Contributing

Issues and PRs welcome at [github.com/ShulkwiSEC/bugbounty.sa/issues](https://github.com/ShulkwiSEC/bugbounty.sa/issues). Keep `bbsa reports push` the only code path that submits, and keep it out of the MCP server — no new dependencies without a good reason.

## License

[Apache-2.0](LICENSE) — full text in [`LICENSE`](LICENSE).
