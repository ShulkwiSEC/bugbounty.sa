# bbsa — working notes

CLI (`bbsa`) + MCP server (`bbsa-mcp`) for bugbounty.sa. Python 3.12, `uv`, no
framework. `src/bbsa/` is the package; the distribution is named `bugbounty.sa`.

## Report submission: the one rule

Everything reads except report submission. Submission is deliberately two steps:

```
bbsa reports draft report.md                     # local Markdown file, sends nothing
BBSA_ALLOW_PUSH=1 bbsa reports push d1 --agree   # the only code path that sends
```

**Always draft first. Never push unless the user explicitly asks you to submit
that draft.** Being asked to write up a finding is not being asked to file it.
Draft it, show them what it says, and let them decide.

This matters because there is no undo: the platform gates `editReport` to admins
and triagers, so a researcher cannot edit, withdraw, or delete a submitted
report. Never file a test, sample, or placeholder report — drafts are local and
free, use those.

Three backstops, because an instruction in a skill file is not a control. Keep
all three:

- **`BBSA_ALLOW_PUSH` is off by default.** `submit.submit_report` refuses and
  raises `push_disabled` before any network call. Drafting, review and
  `--dry-run` are never gated. Pass it inline on the one command that submits;
  never export it, never put it in a profile, `.env`, or settings file, and
  never add it to an agent's allowlist.
- **The MCP server has no submit tool.** `draft_report` writes to disk; there is
  no `submit_report`. Do not add one.
- **`--agree` is required on push and never defaulted.** The three agreement
  booleans are legal acknowledgements — the user ticks them, not us.

Be honest about what this is: a safety catch, not a security boundary. Anything
that can run the CLI can set the variable. It buys a fail-closed default and
makes a real submission a deliberate, greppable act.

## Testing without touching the platform

- `BBSA_API_URL` repoints the HTTP client at a local mock server.
  `tests/test_submit_wire.py` uses it to assert the real request. Only ever
  point it at a host you control — the bearer token follows it.
- `BBSA_DRAFT_DIR` repoints the draft store.
- `bbsa reports push --dry-run` renders the payload and sends nothing.

```bash
PYTHONPATH=tests python -m unittest test_reports test_submit test_submit_wire test_drafts
```

## Layout

| File | Role |
|---|---|
| `api.py` | the only HTTP layer; `get` everywhere, `post` only for submission |
| `submit.py` | payload building + local validation mirroring the web form |
| `richtext.py` | Markdown → the Quill HTML subset the platform stores |
| `drafts.py` | local draft store: Markdown + `key: value` frontmatter |
| `vuln_types.json` | 228 vulnerability types, extracted from the web bundle |
| `cli/commands/*` | one module per resource |
| `SKILL.md` | shipped agent skill; auto-installed by `skill.py` |

## Facts about the platform, learned from its JS bundle

The API is undocumented; these were read out of `bugbounty.sa`'s SPA and are the
reason the code looks the way it does. Re-check them against the live bundle
before assuming they still hold.

- `POST /programs/{id}/reports` — body: `title, domain, endpoint, type,
  parameter, summary, poc, impact, remediation, attachments, agreement1..3,
  recaptchaToken`.
- Report bodies are **rich text, not Markdown**. The editor is Quill and stores
  HTML, capped at 5000 characters of HTML per field. Raw Markdown renders as
  literal `**asterisks**`, hence `richtext.py`.
- Quill's toolbar offers only h3/h4, bold, underline, strike, blockquote,
  code-block, lists, align, color, image, link — so that is the target tag set.
  `richtext.py` also emits `em` and inline `code`, which render but have no
  toolbar button. Stay inside the set or reports stop being editable in the web UI.
- Vulnerability types are hardcoded in the frontend; there is no endpoint.
- `recaptchaToken` is attached to every write by the web app. We send `null`,
  which is what the browser sends without grecaptcha. **Unverified against a real
  submission** — if pushes start failing, suspect this first.
- Attachments upload via `POST /uploads` (multipart `file` + `type=reports` —
  the report form's bucket; `bug_reports` is a different bucket the submit
  rejects), returning an id that goes in `attachments`. The endpoint accepts
  **only `image/png`, `image/jpeg`, `application/pdf`, max 5 files** for report
  attachments; anything else 422s *after* the upload, so `submit.check_attachments`
  rejects it locally first. PoC scripts and text/JSON evidence go inline in the
  body, not as attachments. Draft `--attach` paths stay local; files upload only
  during an explicitly authorized push.

## Conventions

- Every command takes `--json` and emits `{ok, data, meta}`; errors go to stderr.
- Exit codes: `0` ok, `1` error, `2` usage, `3` not found.
- Color only on a TTY; tab-separated when piped.
- Deliberate shortcuts are marked with a `ponytail:` comment naming the ceiling.
- No new dependencies without a good reason. Current set: `mcp`, `httpx`, `rich`.
