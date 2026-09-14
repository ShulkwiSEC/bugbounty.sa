---
name: bbsa
description: CLI and MCP server for the bugbounty.sa bug bounty platform (PyPI package bugbounty.sa; executables bbsa and bbsa-mcp). This skill should be used when the user asks to read data from bugbounty.sa — their researcher profile, bug bounty programs, reports, invoices, finance, transactions, leaderboard, companies, or notifications — to draft a new vulnerability report for the user to review and submit, or needs help setting up or troubleshooting the bbsa token and MCP server. Triggers on "bbsa", "bugbounty.sa", "check my reports", "list programs", "submit a report", "draft a report", "file a bug bounty report", "my leaderboard", "bug bounty platform", "bugbounty.sa MCP". Provides exact CLI commands, MCP tool mappings, and JSON output patterns.
license: Apache-2.0
---

# bbsa — bugbounty.sa CLI + MCP

bbsa is a CLI (`bbsa`) and MCP server (`bbsa-mcp`) for bugbounty.sa. Reading is unrestricted. Submitting is two steps: `bbsa reports draft` saves a Markdown file locally, and only `bbsa reports push` sends it.

**Always draft first, and never push unless the user asks you to.** Every report begins as a local draft the user can read. Pushing is a separate, explicit step: run `bbsa reports push` only when the user has asked for that specific draft to be submitted. If they have not asked, hand them the command instead.

Two things enforce this beyond the instruction: the MCP server has **no submit tool** (`draft_report` writes to the user's disk and nothing else), and `bbsa reports push` **refuses to send unless `BBSA_ALLOW_PUSH=1` is set**. Drafting is never gated. A submitted report cannot be edited or withdrawn by a researcher.

Do not set `BBSA_ALLOW_PUSH` yourself, do not add it to the user's shell profile, and do not suggest exporting it. If the user asks you to submit a draft, run it inline for that one command:

```bash
BBSA_ALLOW_PUSH=1 bbsa reports push d1 --agree
```

## When to use

Use when the user wants data from bugbounty.sa: profile, programs, reports, invoices, finance, leaderboard, companies, or notifications; when they want a report drafted for a program; or when they need the token/MCP setup.

**Not for**: editing or deleting platform data, or commenting on reports. The package exposes no such endpoints.

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

`list_programs`, `get_program_scope`, `list_reports`, `get_report`, `get_report_stats`, `list_vulnerability_types`, `list_submission_agreements`, `list_drafts`, `draft_report`, `get_wallet_balance`, `list_invoices`, `get_invoice_stats`, `list_transactions`, `get_transaction_stats`, `get_public_leaderboard`, `list_companies`, `get_company`, `list_notifications`. Resource: `bugbounty://me/profile`.

- `list_reports` returns each report's numeric `id` and slug.
- `get_report(report_id_or_slug)` accepts either value and includes follow-up comments in `data.comments`.
- `draft_report(...)` is the only writing tool and it writes locally — there is no MCP tool that submits. Its `summary`/`poc`/`impact`/`remediation` arguments take Markdown and are converted to rich text at push time. After calling it, give the user the draft id and file path, and let them review it (`bbsa reports show <id>`) before anything is pushed.

## Drafting a report

`bbsa reports draft` reads one Markdown file and saves it locally. The `# ` heading becomes the title; the body comes from `## Summary`, `## Proof of Concept`, `## Impact` and `## Remediation` sections — the same layout `bbsa reports show` prints, so an existing report round-trips. Metadata lives in `key: value` frontmatter or comes from flags.

```bash
bbsa reports types --search xss            # exact --type values live here
bbsa reports draft --program 1475 \
  --domain https://example.com --endpoint /api/v1/users \
  --type 'Reflected - Non-Self' --parameter q \
  --attach poc.py --attach evidence.har report.md
bbsa reports show d1                       # review; says whether it is ready
BBSA_ALLOW_PUSH=1 bbsa reports push d1 --agree   # only when the user asks
```

Drafts live in `$XDG_DATA_HOME/bbsa/drafts` as plain Markdown, appear in `bbsa reports list` tagged `draft`, and are archived to `drafts/pushed/` once submitted. `bbsa reports show <draft-id>` reports what still blocks a push.

**Re-drafting is idempotent.** A new draft that shares a pending draft's program *and* title overwrites it instead of creating a second copy, so you can iterate on a finding — fix wording, add a PoC, tighten the impact — by drafting it again without piling up `d4`/`d5` duplicates. Keep the `# Title` line stable across revisions of the same finding; change it and you get a new draft. To fork into a genuinely different report, give it a different title.

**bugbounty.sa does not render Markdown.** Its report fields are rich text (a Quill editor) that store HTML, so raw Markdown would show up as literal `**asterisks**`. bbsa converts for you into the tag set the platform's own toolbar produces: `h3`/`h4` headings (all Markdown heading levels fold into those two), `strong`, `em`, `s`, `code`, fenced blocks, blockquotes, ordered/bullet lists, and links. Nested lists flatten to one level and horizontal rules are dropped.

Use repeatable `--attach PATH` when drafting to add evidence. **The platform
accepts only PNG, JPEG and PDF attachments, at most five per report** — a `.py`,
`.txt` or `.json` file is rejected (bbsa now refuses it at draft/push time
instead of failing after a partial upload). So put the executable PoC script and
any text/JSON evidence **inline in the report body** as fenced code blocks, and
`--attach` only screenshots (`.png`) or PDFs. Drafting records and validates the
local paths but uploads nothing; the operator-gated push uploads them first and
sends their returned IDs with the report. Never attach credentials, unredacted
PII, or unrelated files.

The report submission API has no severity field. Include an evidence-backed CVSS
vector and severity in Summary. A platform badge of `Unspecified` remains until
the platform's triage workflow assigns it; bbsa cannot set that badge — do not
promise the user a severity number the platform will show.

## Writing a report a triager wants to read

A report is drafted once and cannot be edited after submission, so make the
first version the good one. The bar is: a triager reproduces the bug from your
words alone, in minutes, and never has to ask a follow-up.

- **Title** — one specific sentence: the bug class, the exact endpoint, and the
  concrete impact. `IDOR in POST /api/v1/bill/get discloses any subscriber's
  partial national-ID digits` beats `IDOR vulnerability`. This is also the draft's
  identity for de-duplication, so keep it stable while iterating.
- **Summary** — what the bug is, where, and why it matters, in a few sentences,
  with the CVSS vector *and* the score you claim (`CVSS:3.1/AV:N/... = 5.3
  (Medium)`) and a one-line justification of the score. Lead with the fact, not
  the story.
- **Proof of Concept** — a copy-pasteable, deterministic reproduction: exact
  request(s) in fenced code blocks (method, path, headers, body), the real
  response showing the leak/effect, and the precondition (auth state, a second
  account, a known id). Include the executable PoC script and its real output
  **inline** in fenced blocks (the platform won't accept a `.py`/`.txt`
  attachment — only PNG/JPEG/PDF). Number the steps. No screenshots as the only
  evidence.
- **Impact** — the realistic worst case for *this* target and who it hurts, tied
  to what the PoC actually proved. Don't inflate; a triager downgrades a report
  that oversells.
- **Remediation** — concrete, ordered fixes the vendor can act on, plus how to
  verify the fix. Name the root cause (missing object-level authz, a secret in a
  client-served file), not just the symptom.
- **Scope & safety** — confirm the target is in the program's scope
  (`programs show <ID>`) before drafting. Redact secrets and PII in the report
  body and in PoC output (last-N digits, `********`); never attach credentials,
  raw PII, or unrelated files. State any deliberate limits you set (e.g. "did not
  attempt login with the disclosed credential").
- **Formatting** — write Markdown; bbsa renders it to the platform's rich text.
  Emphasis, inline `code`, fenced blocks, lists, blockquotes and links all work,
  and emphasis may wrap a `code` span. Each rendered section must stay under 5000
  characters of HTML — `bbsa reports show <draft-id>` tells you if one is over.

## Gotchas

- `bbsa reports push` without `BBSA_ALLOW_PUSH=1` exits with `push_disabled` and sends nothing — that is the default, not a misconfiguration. `--dry-run` works either way.
- Drafting validates the same rules a push does, so a draft that says "Ready to push" will not 422. Validation is local — domain must carry a scheme (`https://example.com`) or be a bare IPv4, endpoint must be a path (`/api/v1/users`), parameter is `[A-Za-z0-9_-]` only, `--type` must match `bbsa reports types` exactly, and each rendered section must stay under 5000 characters of HTML. Fix these before blaming the API.
- **Every command** needs `--json` flag; the flag is not a global option that flips the whole subcommand tree.
- Exit codes are meaningful: `0` ok, `1` error, `2` usage, `3` not found. Check the code before blaming the network.
- `reports list` shows local drafts even when the API is unreachable, but then exits `1` with `meta.remote_error` set. Never report "you have no reports" on a non-zero exit — the fetch failed, the account is not empty.
- ANSI color appears only on a TTY; piped output is tab-separated plain. Use `--no-color` in scripts.
- Never invent report IDs — get the numeric `id` from `reports list`/`list_reports`, then pass it to `reports show`/`get_report`.
- Program end dates and leaderboard positions change over time. Never assert a program's status or a rank from memory.
- Private endpoints fail with `401` when `BUGBOUNTY_SA_TOKEN` is unset — that is the first thing to check.

## Workflows

1. **Investigate open work** — `reports list`, then `reports show` for any still in triage; summarize status, severity, and next step per report.
2. **Recon a program** — `programs list`, then `programs show` the highest-bounty public program; report scope, reward ranges, and domains.
3. **Researcher briefing** — `leaderboard`, `notifications`, and `me`; compare the user's profile to the leaders.
4. **Draft a finding** — `programs show <ID>` to confirm the target is in scope, `reports types --search <keyword>` for the exact type name, then `reports draft ...`. Report the draft id and path and stop there. If the user then asks you to submit it, `BBSA_ALLOW_PUSH=1 reports push <id> --agree`.

## Guardrails

- **Always draft first.** Never construct and push a report in one motion, even when asked to "submit a report" — draft it, show the user what it says, and let them decide.
- **Never push unprompted.** `bbsa reports push` is only for when the user explicitly asks you to submit a named draft. "Draft a report for X" is not a request to push it. When in doubt, print the push command and let them run it.
- **Never persist `BBSA_ALLOW_PUSH`.** It is off by default on purpose. Pass it inline on the single push the user asked for; never export it, add it to a profile, a `.env`, a settings file, or a permission allowlist.
- Reports cannot be edited, withdrawn, or deleted once submitted, and researchers have no edit permission. There is no undo. Never create a test, sample, or placeholder report; drafts are local and free, use those.
- Check the finding is in the program's scope (`programs show <ID>`) before drafting.
- Never edit or delete platform data — the package has no such endpoints.
- Never expose `BUGBOUNTY_SA_TOKEN` in output, logs, or files.
