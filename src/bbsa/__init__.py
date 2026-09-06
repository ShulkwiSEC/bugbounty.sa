"""MCP server for bugbounty.sa — tools + 1 resource.

Every tool here is read-only against bugbounty.sa. `draft_report` writes a local
file and nothing else: this server deliberately has no way to submit a report.

The rule for agents is: always draft first, and never push unless the user asks.
Pushing exists only on the CLI (`bbsa reports push <id> --agree`), so drafting
through this server is always safe. Reports cannot be edited or withdrawn once
submitted, which is why the send is kept out of reach here.

Shares the HTTP layer with the bbsa CLI (see `api.py`), the submission rules
with `submit.py`, and the draft store with `drafts.py`.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from bbsa import drafts as _drafts
from bbsa import submit as _submit
from bbsa.api import get as _get
from bbsa.api import get_report as _get_report
from bbsa.skill import ensure_skill_installed

mcp = MCPServer("bugbounty-sa")


# ── Programs ─────────────────────────────────────────────────────────


@mcp.tool()
def list_programs() -> dict:
    """List active programs on bugbounty.sa."""
    return _get("/programs")


@mcp.tool()
def get_program_scope(program_id: int) -> dict:
    """Get full program detail: scope, policy, reward ranges, domains."""
    return _get(f"/programs/{program_id}")


# ── Reports ──────────────────────────────────────────────────────────


@mcp.tool()
def list_reports() -> dict:
    """List submitted reports; each item includes its numeric report ID."""
    return _get("/reports")


@mcp.tool()
def get_report(report_id_or_slug: str) -> dict:
    """Get report detail and comments by numeric ID or slug."""
    return _get_report(report_id_or_slug)


@mcp.tool()
def list_vulnerability_types(search: str = "") -> dict:
    """List the vulnerability type names `draft_report` accepts, optionally filtered."""
    types = _submit.load_types()
    if search:
        needle = search.lower()
        types = [t for t in types if needle in t["name"].lower() or needle in t["parent"].lower()]
    return {"data": types, "meta": {"total": len(types)}}


@mcp.tool()
def list_submission_agreements() -> dict:
    """The three terms a researcher must accept before a draft can be pushed."""
    return {"data": list(_submit.AGREEMENTS)}


@mcp.tool()
def list_drafts() -> dict:
    """List local report drafts awaiting the user's review, newest first."""
    items = [
        {
            "id": draft_id,
            "title": _submit.parse_report_markdown(body)[0] or "(untitled)",
            "status": "draft",
            "path": str(path),
            **meta,
        }
        for draft_id, meta, body, path in _drafts.load_all()
    ]
    return {"data": items, "meta": {"total": len(items)}}


@mcp.tool()
def draft_report(
    program_id: int,
    title: str,
    domain: str,
    endpoint: str,
    type: str,
    summary: str,
    poc: str,
    impact: str,
    remediation: str,
    parameter: str = "",
) -> dict:
    """Save a report as a LOCAL DRAFT for the user to review. Sends nothing.

    This server cannot submit reports — by design. Write the draft, tell the user
    its id and file path, and let them review it. Only push it (via the CLI,
    `bbsa reports push <id> --agree`) if they explicitly ask you to submit that
    draft; being asked to write a report is not being asked to file it. A
    submitted report cannot be edited or withdrawn by a researcher.

    `summary`, `poc`, `impact` and `remediation` are Markdown; they are converted
    to the platform's rich text at push time. `domain` is a full host like
    https://example.com, `endpoint` a path like /api/v1/users, and `type` an exact
    name from `list_vulnerability_types`.
    """
    # Validate now so the user reviews a draft that will actually push.
    _submit.build_payload(
        title=title,
        domain=domain,
        endpoint=endpoint,
        type=type,
        parameter=parameter,
        agreed=True,  # consent is collected from the human at push time, not here
        summary=summary,
        poc=poc,
        impact=impact,
        remediation=remediation,
    )
    body = "\n\n".join(
        [
            f"# {title}",
            "## Summary",
            summary.strip(),
            "## Proof of Concept",
            poc.strip(),
            "## Impact",
            impact.strip(),
            "## Remediation",
            remediation.strip(),
        ]
    )
    meta = {
        "program": program_id,
        "domain": domain,
        "endpoint": endpoint,
        "type": _submit.resolve_type(type),
        "parameter": parameter,
    }
    draft_id, path = _drafts.save(meta, body)
    return {
        "data": {"id": draft_id, "path": str(path), "status": "draft"},
        "meta": {
            "submitted": False,
            "next_step": f"The user reviews it, then runs: bbsa reports push {draft_id} --agree",
        },
    }


@mcp.tool()
def get_report_stats(group_by: str = "status") -> dict:
    """Dashboard stats: report counts grouped by status/severity/type."""
    return _get("/reports/stats/grouped", {"groupBy": group_by})


# ── Finance ──────────────────────────────────────────────────────────
# ponytail: role-gated — wallet/transactions verified 403 with a researcher
# token (invoices work, that's the researcher payout surface).


@mcp.tool()
def get_wallet_balance() -> dict:
    """Get account wallet balance and total payout stats (company/admin role)."""
    return _get("/wallet/balance")


@mcp.tool()
def list_invoices() -> dict:
    """List bounty invoices."""
    return _get("/invoices")


@mcp.tool()
def get_invoice_stats() -> dict:
    """Invoice summary stats."""
    return _get("/invoices/stats")


@mcp.tool()
def list_transactions() -> dict:
    """List payment/transaction history."""
    return _get("/transactions")


@mcp.tool()
def get_transaction_stats() -> dict:
    """Transaction summary stats."""
    return _get("/transactions/stats")


# ── Leaderboard ───────────────────────────────────────────────────────


@mcp.tool()
def get_public_leaderboard() -> dict:
    """Top 10 researchers leaderboard (public, no auth needed)."""
    return _get("/leaderboard")


# ── Companies ────────────────────────────────────────────────────────
# ponytail: role-gated — verified 403 with a researcher token. Keep for
# admin/company tokens; drop these tools if the server is researcher-only.


@mcp.tool()
def list_companies() -> dict:
    """List companies on the platform."""
    return _get("/companies")


@mcp.tool()
def get_company(company_id: int) -> dict:
    """Get company detail by ID."""
    return _get(f"/companies/{company_id}")


# ── Notifications ────────────────────────────────────────────────────


@mcp.tool()
def list_notifications() -> dict:
    """List notifications (unread count, recent alerts)."""
    return _get("/notifications")


# ── Resource ─────────────────────────────────────────────────────────


@mcp.resource("bugbounty://me/profile")
def get_my_profile() -> dict:
    """Current researcher account profile."""
    return _get("/me")


# ── Entry point ──────────────────────────────────────────────────────


def main() -> None:
    ensure_skill_installed()
    mcp.run()
