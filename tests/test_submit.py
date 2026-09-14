"""Report payload building, validation, and the push gate."""

import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from bbsa import api, richtext, submit
from bbsa.cli.commands.reports import _attachment_paths

REPORT_MD = """# Reflected XSS in search

## Summary
The `q` parameter is reflected **verbatim**.

## Proof of Concept
1. Send the request
2. Watch it fire

## Impact
Session theft.

## Remediation
- Encode output.
"""

VALID = dict(
    agreed=True,
    domain="https://example.com",
    endpoint="/api/v1/users",
    type="Reflected - Non-Self",
    parameter="q",
    summary="s",
    poc="p",
    impact="i",
    remediation="r",
)


class SubmitTest(TestCase):
    def test_missing_draft_attachment_is_rejected(self):
        with self.assertRaises(api.ApiError) as caught:
            _attachment_paths({"attachments": '["/definitely/missing/poc.py"]'})
        self.assertEqual(caught.exception.code, "validation_error")

    def test_parses_title_and_sections(self):
        title, sections = submit.parse_report_markdown(REPORT_MD)
        self.assertEqual(title, "Reflected XSS in search")
        self.assertEqual(sorted(sections), ["impact", "poc", "remediation", "summary"])
        self.assertIn("verbatim", sections["summary"])

    def test_payload_renders_bodies_to_html(self):
        title, sections = submit.parse_report_markdown(REPORT_MD)
        payload = submit.build_payload(
            title=title,
            domain="https://example.com",
            endpoint="/api/v1/users",
            type="reflected - non-self",  # case-insensitive
            parameter="q",
            agreed=True,
            **sections,
        )
        self.assertEqual(payload["type"], "Reflected - Non-Self")
        self.assertEqual(payload["recaptchaToken"], None)
        self.assertEqual(payload["attachments"], [])
        self.assertTrue(all(payload[f"agreement{n}"] for n in (1, 2, 3)))
        self.assertIn("<strong>verbatim</strong>", payload["summary"])
        self.assertIn("<ol><li>", payload["poc"])
        self.assertIn("<ul><li>", payload["remediation"])

    def test_rejects_bad_input_before_the_network(self):
        for override, expected in (
            ({"domain": "example.com"}, "Invalid domain"),
            ({"endpoint": "api/v1/users"}, "Invalid endpoint"),
            ({"parameter": "q;drop"}, "Invalid parameter"),
            ({"type": "Nonsense"}, "Unknown vulnerability type"),
            ({"impact": " "}, "Missing required section"),
            ({"summary": "x" * (richtext.MAX_LEN + 1)}, "limit is"),
        ):
            with self.subTest(**override), self.assertRaises(api.ApiError) as caught:
                submit.build_payload(title="T", **{**VALID, **override})
            self.assertIn(expected, str(caught.exception))
            self.assertEqual(caught.exception.code, "validation_error")

        with self.assertRaises(api.ApiError):
            submit.build_payload(title="  ", **VALID)

    def test_will_not_submit_without_agreement(self):
        with self.assertRaises(api.ApiError) as caught:
            submit.build_payload(title="T", **{**VALID, "agreed": False})
        self.assertIn("three of", str(caught.exception))
        for agreement in submit.AGREEMENTS:
            self.assertIn(agreement, str(caught.exception))

    def test_posts_to_the_program_report_endpoint(self):
        with (
            patch.dict(os.environ, {submit.PUSH_ENV: "1"}),
            patch("bbsa.submit.api.post", return_value={"data": {"id": 7}}) as post,
        ):
            submit.submit_report(1475, {"title": "T"})
        post.assert_called_once_with("/programs/1475/reports", {"title": "T"})

    def test_uploads_attachment_as_report_multipart(self):
        path = Path(tempfile.mkdtemp()) / "evidence.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        response = Mock(status_code=201)
        response.json.return_value = {"data": {"id": 91}}
        with patch("bbsa.api.httpx.post", return_value=response) as post:
            self.assertEqual(api.upload(path), {"data": {"id": 91}})
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["data"], {"type": "reports"})
        self.assertEqual(kwargs["files"]["file"][0], "evidence.png")
        self.assertNotIn("Content-Type", kwargs["headers"])

    def test_upload_rejects_non_image_pdf_report_attachment(self):
        path = Path(tempfile.mkdtemp()) / "poc.py"
        path.write_text("print('proof')", encoding="utf-8")
        with patch("bbsa.api.httpx.post") as post:
            with self.assertRaises(api.ApiError) as ctx:
                api.upload(path)
        self.assertEqual(ctx.exception.code, "validation_error")
        post.assert_not_called()  # fail closed before sending

    def test_check_attachments_allows_png_jpg_pdf_and_caps_at_five(self):
        d = Path(tempfile.mkdtemp())
        ok = []
        for name in ("a.png", "b.jpg", "c.jpeg", "d.pdf"):
            (d / name).write_bytes(b"x")
            ok.append(d / name)
        submit.check_attachments(ok)  # no raise
        with self.assertRaises(api.ApiError):
            submit.check_attachments([d / "e.txt"])
        with self.assertRaises(api.ApiError):
            submit.check_attachments([d / f"{i}.png" for i in range(6)])

    def test_submission_is_off_unless_explicitly_enabled(self):
        for value in ("", "0", "no", "false", "maybe"):
            with self.subTest(value=value), patch.dict(os.environ, {submit.PUSH_ENV: value}):
                self.assertFalse(submit.push_enabled())
                with patch("bbsa.submit.api.post") as post:
                    with self.assertRaises(api.ApiError) as caught:
                        submit.submit_report(1475, {"title": "T"})
                post.assert_not_called()
                self.assertEqual(caught.exception.code, "push_disabled")

        for value in ("1", "true", "YES", "On"):
            with self.subTest(value=value), patch.dict(os.environ, {submit.PUSH_ENV: value}):
                self.assertTrue(submit.push_enabled())
