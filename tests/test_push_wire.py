"""Exercise the real draft→push path — httpx, headers, JSON, error handling —
against a local mock server, so nothing is ever filed on bugbounty.sa.

Reports cannot be deleted once submitted, so this is the only end-to-end check
short of a live submission.
"""

import io
import json
import os
import tempfile
import threading
from argparse import Namespace
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from bbsa import api
from bbsa.cli.commands.reports import cmd_reports_draft, cmd_reports_push

REPORT_MD = """# Reflected XSS in search

## Summary
The `q` parameter is reflected **verbatim**.

## Proof of Concept
1. Send the request.
2. Watch it fire.

## Impact
Session theft.

## Remediation
- Encode output.
"""


class _Recorder(BaseHTTPRequestHandler):
    """Captures one POST and replies with whatever the test asked for."""

    received: dict | None = None
    status = 201
    body: dict = {"data": {"id": 4242, "slug": "recorded-report", "status": "new"}}

    def do_POST(self):  # BaseHTTPRequestHandler dictates this name
        length = int(self.headers.get("Content-Length") or 0)
        _Recorder.received = {
            "path": self.path,
            "headers": dict(self.headers),
            "json": json.loads(self.rfile.read(length) or b"{}"),
        }
        payload = json.dumps(_Recorder.body).encode()
        self.send_response(_Recorder.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass  # keep the test output clean


class PushWireTest(TestCase):
    def setUp(self):
        server = HTTPServer(("127.0.0.1", 0), _Recorder)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)  # cleanups run LIFO: shutdown, then close
        self.addCleanup(server.shutdown)
        host, port = server.server_address

        self.draft_dir = Path(tempfile.mkdtemp())
        env = patch.dict(
            os.environ,
            {
                "BBSA_API_URL": f"http://{host}:{port}",
                "BUGBOUNTY_SA_TOKEN": "test-token",
                "BBSA_DRAFT_DIR": str(self.draft_dir),
                "BBSA_ALLOW_PUSH": "1",
            },
        )
        env.start()
        self.addCleanup(env.stop)

        _Recorder.received = None
        _Recorder.status = 201
        _Recorder.body = {"data": {"id": 4242, "slug": "recorded-report", "status": "new"}}

        source = Path(tempfile.mkdtemp()) / "report.md"
        source.write_text(REPORT_MD, encoding="utf-8")
        self.draft_args = Namespace(
            file=str(source),
            program=1475,
            domain="https://example.com",
            endpoint="/api/v1/users",
            type="Reflected - Non-Self",
            parameter="q",
            title=None,
            json=False,
        )
        self.args = Namespace(id="d1", agree=True, dry_run=False, json=False)

    def _draft(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cmd_reports_draft(self.draft_args), 0)
        # Drafting must never touch the network — that is the whole point.
        self.assertIsNone(_Recorder.received)

    def _run(self):
        self._draft()
        out = io.StringIO()
        with redirect_stdout(out):
            code = cmd_reports_push(self.args)
        return code, out.getvalue()

    def test_sends_the_request_the_web_app_sends(self):
        code, out = self._run()
        self.assertEqual(code, 0)
        sent = _Recorder.received
        self.assertEqual(sent["path"], "/programs/1475/reports")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer test-token")
        self.assertEqual(sent["headers"]["Content-Type"], "application/json")

        body = sent["json"]
        self.assertEqual(body["title"], "Reflected XSS in search")
        self.assertEqual(body["domain"], "https://example.com")
        self.assertEqual(body["endpoint"], "/api/v1/users")
        self.assertEqual(body["type"], "Reflected - Non-Self")
        self.assertEqual(body["parameter"], "q")
        self.assertIsNone(body["recaptchaToken"])
        self.assertEqual(body["attachments"], [])
        self.assertTrue(all(body[f"agreement{n}"] for n in (1, 2, 3)))
        self.assertIn("<strong>verbatim</strong>", body["summary"])
        self.assertIn("<ol><li>", body["poc"])
        for field in ("summary", "poc", "impact", "remediation"):
            self.assertNotIn("**", body[field], f"{field} still contains raw Markdown")

        self.assertIn("4242", out)
        self.assertIn("recorded-report", out)

    def test_push_is_disabled_without_the_opt_in(self):
        self._draft()
        with patch.dict(os.environ, {"BBSA_ALLOW_PUSH": ""}):
            with self.assertRaises(api.ApiError) as caught:
                cmd_reports_push(self.args)
        self.assertEqual(caught.exception.code, "push_disabled")
        self.assertIsNone(_Recorder.received)  # never reached the network
        # The draft survives a refused push.
        self.assertTrue((self.draft_dir / "d1.md").is_file())

    def test_dry_run_works_without_the_opt_in(self):
        self._draft()
        self.args.dry_run = True
        with patch.dict(os.environ, {"BBSA_ALLOW_PUSH": ""}), redirect_stdout(io.StringIO()):
            self.assertEqual(cmd_reports_push(self.args), 0)
        self.assertIsNone(_Recorder.received)

    def test_drafting_alone_sends_nothing(self):
        self._draft()
        self.assertTrue((self.draft_dir / "d1.md").is_file())

    def test_pushed_draft_is_archived_not_lost(self):
        self._run()
        self.assertFalse((self.draft_dir / "d1.md").exists())
        archived = self.draft_dir / "pushed" / "d1.md"
        self.assertTrue(archived.is_file())
        self.assertIn("recorded-report", archived.read_text())

    def test_refuses_to_send_without_agreement(self):
        self.args.agree = False
        with self.assertRaises(api.ApiError):
            self._run()
        self.assertIsNone(_Recorder.received)

    def test_dry_run_sends_nothing(self):
        self.args.dry_run = True
        code, _ = self._run()
        self.assertEqual(code, 0)
        self.assertIsNone(_Recorder.received)

    def test_surfaces_server_field_errors(self):
        _Recorder.status = 422
        _Recorder.body = {
            "message": "The given data was invalid.",
            "errors": {"recaptchaToken": ["The recaptcha token field is required."]},
        }
        with self.assertRaises(api.ApiError) as caught:
            self._run()
        self.assertEqual(caught.exception.code, "validation_error")
        self.assertIn("recaptchaToken", str(caught.exception))
        self.assertIn("required", str(caught.exception))

    def test_submission_survives_an_unarchivable_draft(self):
        """The report is filed and cannot be withdrawn, so a failed tidy-up must
        never cost the user its identifiers."""
        self._draft()
        with patch("bbsa.drafts.archive", side_effect=OSError("read-only file system")):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = cmd_reports_push(self.args)
            out = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIsNotNone(_Recorder.received)  # it really was submitted
        self.assertIn("4242", out)
        self.assertIn("recorded-report", out)
