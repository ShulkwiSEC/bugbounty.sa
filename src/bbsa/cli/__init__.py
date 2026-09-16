"""bbsa — bugbounty.sa CLI: read everything, submit reports.

Divides into a `src/bbsa/api.py` (shared HTTP), a
`formatters.py` (stable JSON, exit codes, tables) and one `commands/*` module
per resource, mirroring the oh-my-ctf CLI conventions.
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version

from bbsa import api
from bbsa.cli.formatters import (
    EXIT_ERROR,
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_USAGE,
    print_json_error,
    red,
    set_color_enabled,
)
from bbsa.cli.commands.finance import cmd_finance_invoices, cmd_finance_stats
from bbsa.cli.commands.me import cmd_me
from bbsa.skill import ensure_skill_installed
from bbsa.cli.commands.misc import cmd_leaderboard, cmd_notifications
from bbsa.cli.commands.programs import cmd_programs_list, cmd_programs_show
from bbsa.cli.commands.reports import (
    cmd_reports_list,
    cmd_reports_show,
    cmd_reports_stats,
    cmd_reports_draft,
    cmd_reports_push,
    cmd_reports_types,
    cmd_reports_delete,
)

__all__ = ["main"]


def _common_flags() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="Emit stable JSON to stdout")
    common.add_argument("--no-color", action="store_true", help="Disable ANSI color output")
    common.add_argument("--debug", action="store_true", help="Show full stack traces on error")
    return common


def build_parser() -> argparse.ArgumentParser:
    common = _common_flags()
    parser = argparse.ArgumentParser(
        prog="bbsa",
        parents=[common],
        description="bbsa: bugbounty.sa CLI — programs, reports (read + submit), finance, leaderboard.",
        epilog="Examples:\n"
        "  bbsa me\n"
        "  bbsa programs list\n"
        "  bbsa programs show 1475\n"
        "  bbsa reports list --limit 25 --json\n"
        "  bbsa reports show <ID-or-slug>\n"
        "  bbsa reports stats --group severity\n"
        "  bbsa reports types --search xss\n"
        "  bbsa reports draft --program 1475 --domain https://x.com \\\n"
        "      --endpoint /api/v1/users --type 'SQL Injection' report.md\n"
        "  bbsa reports delete d1\n"
        "  BBSA_ALLOW_PUSH=1 bbsa reports push d1 --agree\n"
        "  bbsa finance invoices\n"
        "  bbsa finance stats\n"
        "  bbsa leaderboard --json\n"
        "  bbsa notifications\n"
        "\nPipeline-friendly: bbsa leaderboard --json | jq -r '.data[] | \"\\\\(.rank) \\\\(.username)\"'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {version('bugbounty.sa')}")
    sub = parser.add_subparsers(dest="subcommand", title="Commands")

    # me
    p_me = sub.add_parser("me", parents=[common], help="Show your researcher profile")
    p_me.set_defaults(handler=cmd_me)

    # programs
    p_programs = sub.add_parser(
        "programs", parents=[common], help="List programs or show one program's scope"
    )
    programs_sub = p_programs.add_subparsers(dest="programs_subcommand", title="Programs Commands")
    p_pl = programs_sub.add_parser("list", parents=[common], help="List programs")
    p_pl.add_argument("--limit", type=int, default=25, help="Max programs to show (default: 25)")
    p_pl.set_defaults(handler=cmd_programs_list)
    p_ps = programs_sub.add_parser("show", parents=[common], help="Show program scope, policy, reward ranges")
    p_ps.add_argument("id", type=int, help="Program ID")
    p_ps.set_defaults(handler=cmd_programs_show)

    # reports
    p_reports = sub.add_parser(
        "reports", parents=[common], help="List, inspect, or aggregate your reports"
    )
    reports_sub = p_reports.add_subparsers(dest="reports_subcommand", title="Reports Commands")
    p_rl = reports_sub.add_parser("list", parents=[common], help="List your reports")
    p_rl.add_argument("--limit", type=int, default=25, help="Max reports to show (default: 25)")
    p_rl.set_defaults(handler=cmd_reports_list)
    p_rs = reports_sub.add_parser("show", parents=[common], help="Show one report's detail")
    p_rs.add_argument("id", help="Report ID or slug")
    p_rs.set_defaults(handler=cmd_reports_show)
    p_rst = reports_sub.add_parser("stats", parents=[common], help="Report counts grouped by a field")
    p_rst.add_argument(
        "--group",
        choices=("status", "severity", "type"),
        default="status",
        help="Grouping field (default: status)",
    )
    p_rst.set_defaults(handler=cmd_reports_stats)
    p_rt = reports_sub.add_parser(
        "types", parents=[common], help="List the vulnerability types accepted by --type"
    )
    p_rt.add_argument("--search", help="Filter types by substring (category or name)")
    p_rt.set_defaults(handler=cmd_reports_types)
    p_rd = reports_sub.add_parser(
        "draft",
        parents=[common],
        help="Save a report locally for review (sends nothing)",
        description="Save a report as a local draft. The Markdown file supplies the title "
        "as its '# ' heading and the body as '## Summary', '## Proof of Concept', "
        "'## Impact' and '## Remediation' sections — the same layout 'bbsa reports show' "
        "prints. Metadata may live in the file's frontmatter or come from the flags below; "
        "flags win. Nothing is sent until you run 'bbsa reports push'.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_rd.add_argument("file", help="Report Markdown file, or '-' to read stdin")
    p_rd.add_argument("--program", type=int, help="Program ID to submit to")
    p_rd.add_argument("--domain", help="Affected host, e.g. https://example.com")
    p_rd.add_argument("--endpoint", help="Affected path, e.g. /api/v1/users")
    p_rd.add_argument("--type", help="Vulnerability type (see 'bbsa reports types')")
    p_rd.add_argument("--parameter", help="Affected parameter name (optional)")
    p_rd.add_argument("--title", help="Override the file's '# ' heading")
    p_rd.add_argument(
        "--attach", action="append", default=[], metavar="PATH",
        help="Attach a PoC or evidence file at push time (repeatable)",
    )
    p_rd.set_defaults(handler=cmd_reports_draft)

    p_rp = reports_sub.add_parser(
        "push",
        parents=[common],
        help="Submit a reviewed draft to its program (this is the only send)",
        description="Submit a local draft to bugbounty.sa. This cannot be undone: the "
        "platform does not let researchers edit or delete a submitted report. Review with "
        "'bbsa reports show <draft-id>' first; --dry-run prints the exact payload. Pushing is "
        "disabled unless BBSA_ALLOW_PUSH=1 is set. Agents: run this only when explicitly "
        "asked to submit a named draft.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_rp.add_argument("id", help="Draft ID, e.g. d1")
    p_rp.add_argument(
        "--agree",
        action="store_true",
        help="Agree to the platform's three submission terms (required; --dry-run prints them)",
    )
    p_rp.add_argument(
        "--dry-run", action="store_true", help="Render and validate the payload without sending"
    )
    p_rp.set_defaults(handler=cmd_reports_push)

    p_rdel = reports_sub.add_parser(
        "delete",
        parents=[common],
        help="Permanently remove a local draft",
        description="Delete a local draft file. Pushed drafts (in pushed/) are kept — "
        "they are the only local copy of a filed report. Only pending drafts can be deleted.",
    )
    p_rdel.add_argument("id", help="Draft ID, e.g. d1")
    p_rdel.set_defaults(handler=cmd_reports_delete)

    # finance
    p_finance = sub.add_parser(
        "finance", parents=[common], help="Invoices and payout statistics"
    )
    finance_sub = p_finance.add_subparsers(dest="finance_subcommand", title="Finance Commands")
    p_fi = finance_sub.add_parser("invoices", parents=[common], help="List your invoices")
    p_fi.add_argument("--limit", type=int, default=25, help="Max invoices to show (default: 25)")
    p_fi.set_defaults(handler=cmd_finance_invoices)
    p_fs = finance_sub.add_parser("stats", parents=[common], help="Invoice summary stats")
    p_fs.set_defaults(handler=cmd_finance_stats)

    # leaderboard
    p_lb = sub.add_parser("leaderboard", parents=[common], help="Top 10 researchers (public)")
    p_lb.set_defaults(handler=cmd_leaderboard)

    # notifications
    p_nt = sub.add_parser("notifications", parents=[common], help="List your notifications")
    p_nt.add_argument("--limit", type=int, default=25, help="Max notifications (default: 25)")
    p_nt.set_defaults(handler=cmd_notifications)

    return parser


_SUBCOMMAND_CHILDREN = {"programs": ["list", "show"], "reports": ["list", "show", "stats", "types", "draft", "push", "delete"], "finance": ["invoices", "stats"]}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    ensure_skill_installed()

    try:
        parser = build_parser()
        if not argv:
            parser.print_help()
            return EXIT_OK

        args = parser.parse_args(argv)
        if args.no_color:
            set_color_enabled(False)

        if not hasattr(args, "handler"):
            if args.subcommand in _SUBCOMMAND_CHILDREN:
                kids = ", ".join(_SUBCOMMAND_CHILDREN[args.subcommand])
                if args.json:
                    print_json_error(
                        "invalid_arguments",
                        f"Command 'bbsa {args.subcommand}' requires a subcommand ({kids}).",
                    )
                else:
                    sys.stderr.write(
                        f"Error: 'bbsa {args.subcommand}' requires a subcommand: {kids}\n"
                        f"Run 'bbsa {args.subcommand} --help' for details.\n"
                    )
                return EXIT_USAGE
            parser.print_help()
            return EXIT_USAGE

        return args.handler(args)
    except api.ApiError as exc:
        if "--json" in argv:
            print_json_error(exc.code, str(exc), retryable=exc.retryable)
        else:
            sys.stderr.write(red(f"Error: {exc}\n"))
        return EXIT_NOT_FOUND if exc.code == "not_found" else EXIT_ERROR
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except Exception as exc:
        if "--debug" in argv:
            raise
        if "--json" in argv:
            print_json_error("unexpected_error", str(exc), retryable=False)
        else:
            sys.stderr.write(red(f"Error: {exc}\n"))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
