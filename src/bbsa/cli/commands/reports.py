"""bbsa reports list / show / stats / types / draft / push.

Submission is deliberately two steps: `draft` writes a reviewable Markdown file
locally, `push` sends it. Nothing here submits straight from an argument, because
a submitted report cannot be edited or withdrawn.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from bbsa import api, drafts, submit
from bbsa.cli.formatters import (
    EXIT_ERROR,
    EXIT_OK,
    bold,
    dim,
    green,
    print_json_success,
    yellow,
    render_kv,
    red,
    render_table,
    is_color_enabled,
    pick,
    suggest_next_step,
    text,
)
from rich.console import Console
from rich.markdown import Markdown


def _markdown(value: object) -> str:
    """Remove the API's HTML wrappers while preserving embedded Markdown."""
    value = re.sub(r"<(?:br|/p|/div|/li)\b[^>]*>", "\n\n", str(value), flags=re.I)
    value = re.sub(r"<li\b[^>]*>", "- ", value, flags=re.I)
    value = html.unescape(re.sub(r"<[^>]+>", "", value))
    value = re.sub(r"(?m)^[ \N{NO-BREAK SPACE}]*(?=```)", "", value)
    parts = re.split(r"(```.*?```|`[^`\n]*`)", value, flags=re.S)
    return "".join(
        part if i % 2 else part.replace("<", r"\<").replace(">", r"\>")
        for i, part in enumerate(parts)
    ).strip()


def cmd_reports_list(args: argparse.Namespace) -> int:
    pending = drafts.load_all()
    items: list = []
    meta: dict = {}
    remote_error: api.ApiError | None = None
    try:
        resp = api.get("/reports")
        items = resp.get("data") or []
        meta = resp.get("meta") or {}
    except api.ApiError as exc:
        if not pending:
            raise  # nothing local to fall back on, so the failure is the answer
        remote_error = exc

    total = meta.get("total") if meta.get("total") is not None else len(items)
    # ponytail: client-side slice; switch to server page/limit if get large
    shown = items[: args.limit] if args.limit else items

    drafted = [
        {
            "id": draft_id,
            "title": submit.parse_report_markdown(body)[0] or "(untitled)",
            "status": "draft",
            "program": draft_meta.get("program"),
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            "path": str(path),
        }
        for draft_id, draft_meta, body, path in pending
    ]

    listing_meta: dict = {"total": total, "shown": len(shown), "drafts": len(drafted)}
    if remote_error:
        # Never let a failed fetch look like an empty account: callers reading the
        # JSON must be able to tell "no reports" from "could not ask".
        listing_meta["remote_error"] = {
            "code": remote_error.code,
            "message": str(remote_error),
            "retryable": remote_error.retryable,
        }

    if args.json:
        print_json_success(drafted + shown, meta=listing_meta)
        return EXIT_ERROR if remote_error else EXIT_OK
    if not shown and not drafted:
        print(dim("No reports or drafts found."))
        return EXIT_OK

    rows = [
        [
            yellow(d["id"]),
            text(d["title"]),
            yellow("draft"),
            "-",
            d["updated_at"],
        ]
        for d in drafted
    ]
    rows += [
        [
            str(r.get("id", "-")),
            text(pick(r, "title", "name", default="-")),
            text(pick(r, "status", default="-")),
            text(pick(r, "severity", default="-")),
            str(pick(r, "created_at", "updated_at", default="-")),
        ]
        for r in shown
    ]
    print(render_table(["ID", "TITLE", "STATUS", "SEVERITY", "UPDATED"], rows))

    if remote_error:
        sys.stderr.write(
            red(
                f"\nLocal drafts only — could not reach bugbounty.sa: {remote_error}\n",
                sys.stderr,
            )
        )
        return EXIT_ERROR

    if drafted:
        suggest_next_step(f"bbsa reports show {drafted[0]['id']} to review before pushing")
    elif len(shown) < total:
        suggest_next_step(f"Showing {len(shown)} of {total} — see all with --limit {total}")
    else:
        suggest_next_step("bbsa reports show <ID-or-slug> for detail")
    return EXIT_OK


def cmd_reports_show(args: argparse.Namespace) -> int:
    if drafts.is_draft_id(args.id):
        return _show_draft(args)
    r = api.get_report(args.id)["data"]
    comments = r.pop("comments", [])
    if args.json:
        print_json_success({**r, "comments": comments})
        return EXIT_OK

    fields = [
        ("ID", r.get("id")),
        ("Status", text(r.get("status", "-"))),
        ("Severity", r.get("severity")),
        ("Program", text(r.get("program", ""))),
        ("Type", r.get("type")),
        ("Domain", r.get("domain")),
        ("Endpoint", r.get("endpoint")),
        ("Parameter", r.get("parameter")),
        ("Created", r.get("created_at")),
        ("Updated", r.get("updated_at")),
    ]
    lines = [f"# {_markdown(pick(r, 'title', 'name', default=f'Report {args.id}'))}"]
    lines.extend(f"- **{key}:** {_markdown(value)}" for key, value in fields if value)

    for heading, keys in (
        ("Summary", ("summary",)),
        ("Description", ("description", "body")),
        ("Proof of Concept", ("poc", "reproduction_steps")),
        ("Impact", ("impact",)),
        ("Remediation", ("remediation",)),
    ):
        content = pick(r, *keys, default="")
        if content:
            lines.extend((f"\n## {heading}\n", _markdown(content)))

    lines.append("\n## Comments")
    if not comments:
        lines.append("\n_No comments._")
    for comment in comments:
        author = comment.get("from_user") or {}
        name = author.get("username") or author.get("first_name") or author.get("type") or "Unknown"
        lines.extend(
            (
                f"\n### {_markdown(name)} · {_markdown(comment.get('created_at', ''))}\n",
                _markdown(comment.get("content", "")) or "_Empty comment._",
            )
        )

    Console(no_color=not is_color_enabled()).print(Markdown("\n".join(lines)))
    return EXIT_OK


def cmd_reports_stats(args: argparse.Namespace) -> int:
    resp = api.get("/reports/stats/grouped", {"groupBy": args.group})
    payload = resp.get("data", resp)
    if args.json:
        print_json_success(payload, meta={"group_by": args.group})
        return EXIT_OK

    if isinstance(payload, dict):
        print(bold(f"══ Report Stats (by {args.group}) ══\n"))
        print(render_kv([(str(k), str(v)) for k, v in payload.items()]))
    elif isinstance(payload, list):
        rows = []
        for x in payload:
            if isinstance(x, dict):
                rows.append([str(pick(x, "group", args.group, default="-")), str(x.get("count", "-"))])
            else:
                rows.append([str(x), "?"])
        print(render_table([args.group.title(), "COUNT"], rows))
    else:
        print(str(payload))
    suggest_next_step(r"jq filter: bbsa reports stats --json | jq '.data'")
    return EXIT_OK


def cmd_reports_types(args: argparse.Namespace) -> int:
    types = submit.load_types()
    if args.search:
        needle = args.search.lower()
        types = [t for t in types if needle in t["name"].lower() or needle in t["parent"].lower()]

    if args.json:
        print_json_success(types, meta={"total": len(types)})
        return EXIT_OK
    if not types:
        print(dim(f"No vulnerability type matches {args.search!r}."))
        return EXIT_OK

    print(render_table(
        ["CATEGORY", "TYPE"],
        [[text(t["parent"], 45), text(t["name"], 60)] for t in types],
    ))
    suggest_next_step("Pass the TYPE column value verbatim to 'bbsa reports draft --type'")
    return EXIT_OK


def _load_draft(draft_id: str):
    try:
        return drafts.load(draft_id)
    except FileNotFoundError as exc:
        raise api.ApiError(str(exc), code="not_found", status=404) from exc


def _payload_from_draft(meta: dict, body: str, agreed: bool) -> dict:
    title, sections = submit.parse_report_markdown(body)
    return submit.build_payload(
        title=meta.get("title") or title,
        domain=meta.get("domain", ""),
        endpoint=meta.get("endpoint", ""),
        type=meta.get("type", ""),
        parameter=meta.get("parameter", ""),
        agreed=agreed,
        **{f: sections.get(f, "") for f in ("summary", "poc", "impact", "remediation")},
    )


def _attachment_paths(meta: dict) -> list[Path]:
    raw = meta.get("attachments", "")
    if not raw:
        return []
    try:
        paths = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise api.ApiError(
            "Draft 'attachments' must be a JSON list of file paths.", code="validation_error"
        ) from exc
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise api.ApiError(
            "Draft 'attachments' must be a JSON list of file paths.", code="validation_error"
        )
    files = [Path(path).expanduser() for path in paths]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise api.ApiError(
            f"Attachment is not a file: {', '.join(missing)}", code="validation_error"
        )
    submit.check_attachments(files)
    return files


def _draft_blocker(meta: dict, body: str) -> str | None:
    """What still stands between this draft and a successful push, if anything."""
    program = str(meta.get("program", "")).strip()
    if not program.isdigit():
        return "No program set. Add 'program: <ID>' to the draft's frontmatter."
    try:
        # A dry build only renders and validates; consent is asked for at push time.
        _payload_from_draft(meta, body, agreed=True)
        _attachment_paths(meta)
    except api.ApiError as exc:
        return str(exc)
    return None


def _show_draft(args: argparse.Namespace) -> int:
    meta, body, path = _load_draft(args.id)
    title, sections = submit.parse_report_markdown(body)
    blocker = _draft_blocker(meta, body)

    if args.json:
        print_json_success({
            "id": args.id,
            "status": "draft",
            "title": title,
            "path": str(path),
            **meta,
            "sections": sections,
            "ready": blocker is None,
            "blocker": blocker,
        })
        return EXIT_OK

    lines = [f"# {_markdown(title or f'Draft {args.id}')}", ""]
    lines.append("- **Status:** draft (local only — nothing has been sent)")
    lines.extend(f"- **{key.title()}:** {_markdown(value)}" for key, value in meta.items() if value)
    lines.append(f"- **File:** {path}")
    for heading, field in (
        ("Summary", "summary"),
        ("Proof of Concept", "poc"),
        ("Impact", "impact"),
        ("Remediation", "remediation"),
    ):
        content = sections.get(field)
        lines.extend((f"\n## {heading}\n", content if content else "_Missing._"))

    Console(no_color=not is_color_enabled()).print(Markdown("\n".join(lines)))
    if blocker:
        print(yellow(f"\nNot ready to push: {blocker}"))
        suggest_next_step(f"Edit {path}, then re-run this command")
    elif submit.push_enabled():
        print(green("\nReady to push."))
        suggest_next_step(f"bbsa reports push {args.id} --agree")
    else:
        print(green("\nReady to push.") + dim(f" (pushing needs {submit.PUSH_ENV}=1)"))
        suggest_next_step(f"{submit.PUSH_ENV}=1 bbsa reports push {args.id} --agree")
    return EXIT_OK


def cmd_reports_draft(args: argparse.Namespace) -> int:
    raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    meta, body = drafts.parse(raw)
    if not body.strip():
        raise api.ApiError("The report file is empty.", code="validation_error")
    for key in drafts.META_KEYS:
        value = getattr(args, key, None)
        if value not in (None, ""):
            meta[key] = str(value)
    if args.title:
        meta["title"] = args.title
    if getattr(args, "attach", None):
        meta["attachments"] = json.dumps([str(Path(path).resolve()) for path in args.attach])

    draft_id, path = drafts.save(meta, body)
    blocker = _draft_blocker(meta, body)

    if args.json:
        print_json_success(
            {"id": draft_id, "path": str(path), "ready": blocker is None, "blocker": blocker},
            meta={"submitted": False},
        )
        return EXIT_OK

    print(green(f"Draft {draft_id} saved — nothing has been sent."))
    print(render_kv([("File", str(path)), ("Program", str(meta.get("program", "-")))]))
    if blocker:
        print(yellow(f"\nNot ready to push: {blocker}"))
        suggest_next_step(f"Edit {path}, then 'bbsa reports show {draft_id}'")
    else:
        suggest_next_step(f"bbsa reports show {draft_id} to review before pushing")
    return EXIT_OK


def cmd_reports_push(args: argparse.Namespace) -> int:
    meta, body, path = _load_draft(args.id)
    program = str(meta.get("program", "")).strip()
    if not program.isdigit():
        raise api.ApiError(
            f"Draft {args.id} has no program set. Add 'program: <ID>' to {path}.",
            code="validation_error",
        )
    payload = _payload_from_draft(meta, body, agreed=args.agree or args.dry_run)
    attachment_paths = _attachment_paths(meta)

    if args.dry_run:
        if args.json:
            print_json_success(
                {**payload, "attachment_paths": [str(path) for path in attachment_paths]},
                meta={"program_id": int(program), "submitted": False},
            )
        else:
            print(bold(f"══ Dry run — nothing sent to program {program} ══\n"))
            print(render_kv([(k, text(v, 100)) for k, v in payload.items() if v]))
            if attachment_paths:
                print(render_kv([("Attachments", ", ".join(map(str, attachment_paths)))]))
            print(f"\n{bold('Pushing means agreeing to:')}")
            for agreement in submit.AGREEMENTS:
                print(f"  • {agreement}")
            prefix = "" if submit.push_enabled() else f"{submit.PUSH_ENV}=1 "
            suggest_next_step(f"{prefix}bbsa reports push {args.id} --agree")
        return EXIT_OK

    if not submit.push_enabled():
        submit.submit_report(int(program), payload)  # raises before any upload
    uploaded = [api.upload(path).get("data") for path in attachment_paths]
    payload["attachments"] = [
        item.get("id") if isinstance(item, dict) else item for item in uploaded
    ]
    if any(item in (None, "") for item in payload["attachments"]):
        raise api.ApiError("Attachment upload returned no ID.", code="http_error")

    report = submit.submit_report(int(program), payload).get("data") or {}

    # The report is filed and cannot be withdrawn from here on, so nothing below
    # may raise: a failed tidy-up must not cost the user the report's identifiers.
    try:
        archived: Path | None = drafts.archive(args.id, report)
        archive_error = None
    except OSError as exc:
        archived, archive_error = None, str(exc)

    if args.json:
        print_json_success(
            {
                **report,
                "draft_id": args.id,
                "archived_to": str(archived) if archived else None,
                "archive_error": archive_error,
            },
            meta={"program_id": int(program), "submitted": True},
        )
        return EXIT_OK

    print(green(f"Draft {args.id} pushed to program {program}."))
    print(render_kv([
        ("ID", str(report.get("id", "-"))),
        ("Slug", str(report.get("slug", "-"))),
        ("Status", text(report.get("status", "-"))),
        ("Local copy", str(archived) if archived else f"{path} (left in place)"),
    ]))
    if archive_error:
        sys.stderr.write(
            yellow(f"\nReport was submitted, but the draft could not be archived: "
                   f"{archive_error}\n", sys.stderr)
        )
    suggest_next_step(f"bbsa reports show {report.get('slug') or report.get('id')}")
    return EXIT_OK
