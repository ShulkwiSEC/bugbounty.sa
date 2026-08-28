import io
from argparse import Namespace
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch

from bbsa.cli.commands.reports import _markdown, cmd_reports_show


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
