"""Report submission: payload building, validation, POST.

The one write path in the package. `submit_report` is reached only from
`bbsa reports push`; the MCP server has no route to it. Payload building and
validation are shared with `draft_report`, so a draft that validates will push.

Endpoint and rules are taken from the live bugbounty.sa web app:
``POST /programs/{program_id}/reports`` with a JSON body of
``title, domain, endpoint, type, parameter, summary, poc, impact, remediation``,
plus ``attachments`` and the three ``agreement1/2/3`` booleans the web form's
last step requires.
The four body fields are rich text — see `bbsa.richtext`. The field regexes and
the vulnerability taxonomy (`vuln_types.json`, 228 entries) mirror the ones the
web form validates against, so a bad report fails here instead of as a 422.
"""

from __future__ import annotations

import difflib
import functools
import json
import os
import re
from pathlib import Path

from bbsa import api, richtext

__all__ = [
    "AGREEMENTS",
    "PUSH_ENV",
    "SECTIONS",
    "push_enabled",
    "load_types",
    "resolve_type",
    "parse_report_markdown",
    "build_payload",
    "submit_report",
]

# Mirrors the web form's yup schema regexes.
_DOMAIN = re.compile(r"^(http[s]?://(www\.)?)([0-9A-Za-z\-*.@:%_+~#=]+)+(\.[a-zA-Z]{2,3})$")
_IP = re.compile(r"^(?!.*\.$)((?!0\d)(1?\d?\d|25[0-5]|2[0-4]\d)(\.|$)){4}$")
_ENDPOINT = re.compile(r"^[/]$|^(/[A-Za-z0-9\-*.@:%_+~#=]+)+(?!/)$", re.I)
_PARAMETER = re.compile(r"^[a-zA-Z0-9_-]*$")

# Markdown ``## heading`` → API field. Aliases match what `bbsa reports show` prints.
SECTIONS: dict[str, str] = {
    "summary": "summary",
    "description": "summary",
    "proof of concept": "poc",
    "poc": "poc",
    "steps to reproduce": "poc",
    "reproduction steps": "poc",
    "impact": "impact",
    "remediation": "remediation",
    "mitigation": "remediation",
    "fix": "remediation",
}

_BODY_FIELDS = ("summary", "poc", "impact", "remediation")

# The three checkboxes the web form requires before its Submit button enables.
# They are sent as booleans in the report body, so the CLI has to ask too.
AGREEMENTS: tuple[str, ...] = (
    "I hereby agree to the Terms & Conditions and the Privacy and Security Policy.",
    "I hereby agree not to disclose or use any confidential information belonging to "
    "the other party for any reason which is not stated in terms and conditions.",
    "I hereby agree to have the report evaluated by the platform and the bounty will be "
    "determined based on the severity of the bug, impact and quality of the report.",
)


# Pushing is off unless the environment says otherwise, so that an accidental or
# hallucinated `reports push` fails instead of filing an unretractable report.
# Drafting is never gated. This is a safety catch, not a security boundary:
# anything that can run the CLI can also set the variable. Its job is to make a
# submission a deliberate, greppable act rather than one command among many.
PUSH_ENV = "BBSA_ALLOW_PUSH"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def push_enabled() -> bool:
    return os.environ.get(PUSH_ENV, "").strip().lower() in _TRUTHY


def _bad(message: str) -> api.ApiError:
    return api.ApiError(message, code="validation_error", retryable=False)


@functools.cache
def load_types() -> list[dict]:
    """The vulnerability taxonomy the web form's type dropdown offers."""
    return json.loads(Path(__file__).with_name("vuln_types.json").read_text(encoding="utf-8"))


def resolve_type(name: str) -> str:
    """Exact type name as the API expects it. Raises with suggestions if unknown."""
    names = [t["name"] for t in load_types()]
    lowered = {n.lower(): n for n in names}
    exact = lowered.get(str(name).strip().lower())
    if exact:
        return exact
    close = difflib.get_close_matches(str(name), names, n=3, cutoff=0.5)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    raise _bad(
        f"Unknown vulnerability type {name!r}.{hint} List them with 'bbsa reports types'."
    )


def parse_report_markdown(markdown: str) -> tuple[str, dict[str, str]]:
    """Split a report Markdown file into its title and its ``## `` sections."""
    title_match = re.search(r"(?m)^#[ \t]+(.+?)\s*$", markdown)
    title = title_match.group(1).strip() if title_match else ""

    parts = re.split(r"(?m)^##[ \t]+(.+?)[ \t]*$", markdown)
    sections: dict[str, str] = {}
    for heading, body in zip(parts[1::2], parts[2::2]):
        field = SECTIONS.get(heading.strip().lower())
        if field and body.strip():
            sections[field] = body.strip()
    return title, sections


def build_payload(
    *,
    title: str,
    domain: str,
    endpoint: str,
    type: str,
    summary: str,
    poc: str,
    impact: str,
    remediation: str,
    parameter: str = "",
    attachments: list | None = None,
    agreed: bool = False,
) -> dict:
    """Validate the report and render its body fields to rich-text HTML.

    ``agreed`` stands in for the web form's three agreement checkboxes; the caller
    must obtain it from the user, not default it on their behalf.
    """
    if not agreed:
        raise _bad(
            "Submission requires agreeing to all three of:\n  - "
            + "\n  - ".join(AGREEMENTS)
            + "\nPass --agree (CLI) or agreed=True (MCP) to confirm."
        )
    title = (title or "").strip()
    if not title:
        raise _bad("Report title is required (a '# Title' line, or --title).")

    domain = (domain or "").strip()
    if not (_DOMAIN.fullmatch(domain) or _IP.fullmatch(domain)):
        raise _bad(
            f"Invalid domain {domain!r}: expected a scheme-prefixed host "
            "(https://example.com) or a bare IPv4 address."
        )

    endpoint = (endpoint or "").strip()
    if not _ENDPOINT.fullmatch(endpoint):
        raise _bad(f"Invalid endpoint {endpoint!r}: expected a path like /api/v1/users or /.")

    parameter = (parameter or "").strip()
    if not _PARAMETER.fullmatch(parameter):
        raise _bad(f"Invalid parameter {parameter!r}: letters, digits, '_' and '-' only.")

    bodies = {"summary": summary, "poc": poc, "impact": impact, "remediation": remediation}
    missing = [f for f in _BODY_FIELDS if not (bodies[f] or "").strip()]
    if missing:
        headings = ", ".join(f"'## {h.title()}'" for h in missing)
        raise _bad(f"Missing required section(s): {headings}.")

    payload = {
        "title": title,
        "domain": domain,
        "endpoint": endpoint,
        "type": resolve_type(type),
        "parameter": parameter,
        # Upload IDs from POST /uploads; the web form sends [] when nothing is attached.
        "attachments": list(attachments or []),
        "agreement1": True,
        "agreement2": True,
        "agreement3": True,
        # The web app sends this key on every write; grecaptcha-less clients send null.
        "recaptchaToken": None,
    }
    for field in _BODY_FIELDS:
        rendered = richtext.to_html(bodies[field])
        if len(rendered) > richtext.MAX_LEN:
            raise _bad(
                f"Section '{field}' renders to {len(rendered)} characters of HTML; "
                f"the platform's limit is {richtext.MAX_LEN}."
            )
        payload[field] = rendered
    return payload


def submit_report(program_id: int, payload: dict) -> dict:
    """POST a built payload to a program. The only write this package makes.

    Refuses unless `PUSH_ENV` is set — see the note above `push_enabled`.
    """
    if not push_enabled():
        raise api.ApiError(
            f"Pushing is disabled by default, so nothing was sent. Drafting always "
            f"works; submitting a report needs {PUSH_ENV}=1 in the environment:\n\n"
            f"    {PUSH_ENV}=1 bbsa reports push <id> --agree\n\n"
            "Set it inline when you mean to submit rather than in your shell profile — "
            "a submitted report cannot be edited or withdrawn.",
            code="push_disabled",
            retryable=False,
        )
    return api.post(f"/programs/{int(program_id)}/reports", payload)
