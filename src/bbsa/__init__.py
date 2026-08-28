"""Read-only MCP server for bugbounty.sa — tools + 1 resource.

Shares the HTTP layer with the bbsa CLI (see `api.py`).
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

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
