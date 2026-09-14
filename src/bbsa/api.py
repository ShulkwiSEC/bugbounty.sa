"""Shared HTTP layer for bugbounty.sa — used by both the MCP server and the CLI.

Reads are GET; the one write is POST /programs/{id}/reports (report submission).
"""

from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path

import httpx

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BASE_URL = "https://api.bugbounty.sa/api"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Accept-Language": "en",
    "tz": "Asia/Riyadh",
}


def _base_url() -> str:
    """Where requests go. ``BBSA_API_URL`` repoints the client at a local mock
    server so the write path can be exercised without filing a real report.

    Test seam only: the bearer token is sent to whatever this resolves to, so
    never point it at a host you do not control.
    """
    return os.environ.get("BBSA_API_URL", BASE_URL).rstrip("/")


class ApiError(Exception):
    """Raised on any failed request. code + retryable let consumers act on it."""

    def __init__(
        self,
        message: str,
        code: str = "api_error",
        retryable: bool = False,
        status: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status = status


def _err_text(r: httpx.Response) -> str:
    try:
        body = r.json()
        msg = body.get("message") or ""
        errors = body.get("errors") or {}
        if isinstance(errors, dict) and errors:
            detail = "; ".join(
                f"{field}: {v[0] if isinstance(v, list) and v else v}"
                for field, v in errors.items()
            )
            return f"{msg} ({detail})" if msg else detail
        return msg or r.text[:200]
    except Exception:
        return r.text[:200]


def _request(method: str, path: str, params: dict | None = None, json: dict | None = None) -> dict:
    """Single request helper. Returns the full JSON envelope. Raises ApiError."""
    token = os.environ.get("BUGBOUNTY_SA_TOKEN", "")
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.request(
            method, f"{_base_url()}{path}", params=params, json=json, headers=headers, timeout=30
        )
    except httpx.HTTPError as exc:
        raise ApiError(
            f"Request to {path} failed: {exc}", code="network_error", retryable=True
        ) from exc

    if r.status_code < 400:
        return r.json()

    msg = _err_text(r)
    if r.status_code == 401:
        raise ApiError(
            "Unauthenticated. Set BUGBOUNTY_SA_TOKEN to a bugbounty.sa bearer token.",
            code="unauthenticated",
            retryable=True,
            status=401,
        )
    if r.status_code == 403:
        raise ApiError(
            msg or "Forbidden — this token's role lacks access to the endpoint.",
            code="forbidden",
            retryable=False,
            status=403,
        )
    if r.status_code == 404:
        raise ApiError(msg or "Not Found.", code="not_found", retryable=False, status=404)
    if r.status_code == 422:
        raise ApiError(msg or "Validation failed.", code="validation_error", status=422)
    raise ApiError(
        msg or "API error.",
        code="http_error",
        retryable=r.status_code >= 500,
        status=r.status_code,
    )


def get(path: str, params: dict | None = None) -> dict:
    return _request("GET", path, params=params)


def post(path: str, payload: dict) -> dict:
    return _request("POST", path, json=payload)


def upload(path: str | Path, type: str = "reports") -> dict:
    """Upload one report attachment and return the API envelope.

    ``type`` is the ``POST /uploads`` bucket. Report attachments use ``reports``
    (from the web app's upload-type enum); ``bug_reports`` uploads are a
    different bucket the report form does not accept, so the later submit 422s.
    """
    file = Path(path).expanduser()
    if not file.is_file():
        raise ApiError(f"Attachment is not a file: {file}", code="validation_error")
    mime = mimetypes.guess_type(file.name)[0]
    if type == "reports" and mime not in ("image/jpeg", "image/png", "application/pdf"):
        # Backstop: the platform 422s a non-image/PDF report attachment after the
        # upload. Fail closed before sending. submit.check_attachments catches this
        # earlier with fuller guidance; this guards direct api.upload callers.
        raise ApiError(
            f"Report attachment {file.name!r} is {mime or 'an unrecognised type'}; "
            "bugbounty.sa accepts only PNG, JPEG or PDF.",
            code="validation_error",
        )
    token = os.environ.get("BUGBOUNTY_SA_TOKEN", "")
    headers = {k: v for k, v in HEADERS.items() if k.lower() != "content-type"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with file.open("rb") as stream:
            response = httpx.post(
                f"{_base_url()}/uploads",
                data={"type": type},
                files={"file": (file.name, stream, mimetypes.guess_type(file.name)[0])},
                headers=headers,
                timeout=30,
            )
    except httpx.HTTPError as exc:
        raise ApiError(
            f"Upload of {file} failed: {exc}", code="network_error", retryable=True
        ) from exc
    if response.status_code < 400:
        return response.json()
    raise ApiError(
        _err_text(response) or f"Upload of {file} failed.",
        code="validation_error" if response.status_code == 422 else "http_error",
        retryable=response.status_code >= 500,
        status=response.status_code,
    )


def get_report(report_id_or_slug: str) -> dict:
    """Get a report with comments, resolving numeric IDs through the report list."""
    ref = str(report_id_or_slug)
    if ref.isdigit():
        reports = get("/reports").get("data") or []
        report = next((item for item in reports if str(item.get("id")) == ref), None)
        if not report or not report.get("slug"):
            raise ApiError(f"Report {ref} not found.", code="not_found", status=404)
        ref = str(report["slug"])

    response = get(f"/reports/{ref}")
    data = response.get("data")
    if isinstance(data, dict):
        response = {
            **response,
            "data": {
                **data,
                "comments": get(f"/reports/{ref}/comments").get("data") or [],
            },
        }
    return response
