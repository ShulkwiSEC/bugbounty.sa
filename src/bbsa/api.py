"""Shared HTTP layer for bugbounty.sa — used by both the MCP server and the CLI.

Read-only by design: the only verb ever issued is GET.
"""

from __future__ import annotations

import logging
import os

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
        return r.json().get("message") or r.text[:200]
    except Exception:
        return r.text[:200]


def get(path: str, params: dict | None = None) -> dict:
    """Single GET helper. Returns the full JSON envelope. Raises ApiError."""
    token = os.environ.get("BUGBOUNTY_SA_TOKEN", "")
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)
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
    raise ApiError(
        msg or "API error.",
        code="http_error",
        retryable=r.status_code >= 500,
        status=r.status_code,
    )