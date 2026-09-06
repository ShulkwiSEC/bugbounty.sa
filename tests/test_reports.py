import io
import json
import os
import tempfile
from argparse import Namespace
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch

from bbsa import api, drafts
from bbsa.cli.commands.reports import _markdown, cmd_reports_list, cmd_reports_show


class ReportsTest(TestCase):
    def test_report_id_resolves_to_slug_and_fetches_comments(self):
        responses = {
            "/reports": {"data": [{"id": "123", "slug": "friendly-report"}]},
            "/reports/friendly-report": {"data": {"id": "123", "title": "Test", "summary": "<p>Full **text** with &lt;token&gt; and `&lt;code&gt;`</p>"}},
            "/reports/friendly-report/comments": {"data": [{"from_user": {"username": "alice"}, "created_at": "today", "content": "Follow-up"}]},
        }
        output = io.StringIO()

        with (
            patch("bbsa.cli.commands.reports.api.get", side_effect=responses.__getitem__) as get,
            redirect_stdout(output),
        ):
            self.assertEqual(cmd_reports_show(Namespace(id="123", json=False)), 0)

        self.assertEqual([call.args[0] for call in get.call_args_list], list(responses))
        rendered = output.getvalue()
        self.assertIn("Full text", rendered)
        self.assertIn("<token>", rendered)
        self.assertIn("<code>", rendered)
        self.assertIn("Comments", rendered)
        self.assertIn("Follow-up", rendered)
        self.assertEqual(
            _markdown("<p>&lt;script&gt;safe&lt;/script&gt;</p>"),
            r"\<script\>safe\</script\>",
        )


class ReportsListTest(TestCase):
    """A failed remote fetch must never read as an empty account."""

    def setUp(self):
        env = patch.dict(os.environ, {"BBSA_DRAFT_DIR": tempfile.mkdtemp()})
        env.start()
        self.addCleanup(env.stop)
        drafts.save({"program": "1475"}, "# Local finding\n\n## Summary\nx")

    def _list(self, as_json):
        out = io.StringIO()
        with (
            patch(
                "bbsa.cli.commands.reports.api.get",
                side_effect=api.ApiError("boom", code="unauthenticated", retryable=True),
            ),
            redirect_stdout(out),
        ):
            return cmd_reports_list(Namespace(limit=25, json=as_json)), out.getvalue()

    def test_json_reports_the_remote_failure_and_exits_nonzero(self):
        code, out = self._list(as_json=True)
        payload = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(payload["meta"]["drafts"], 1)
        self.assertEqual(payload["meta"]["remote_error"]["code"], "unauthenticated")

    def test_human_output_still_shows_drafts_but_exits_nonzero(self):
        code, out = self._list(as_json=False)
        self.assertEqual(code, 1)
        self.assertIn("Local finding", out)
        self.assertIn("draft", out)

    def test_failure_with_no_drafts_is_just_an_error(self):
        for path in drafts.draft_dir().glob("*.md"):
            path.unlink()
        with self.assertRaises(api.ApiError):
            self._list(as_json=True)
