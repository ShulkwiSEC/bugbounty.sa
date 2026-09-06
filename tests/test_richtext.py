"""The Markdown → Quill-HTML converter."""

from unittest import TestCase

from bbsa import richtext


class RichTextTest(TestCase):
    def test_converter_self_check(self):
        richtext.demo()  # asserts the whole Markdown → Quill-HTML mapping

    def test_markdown_never_survives_as_markdown(self):
        html = richtext.to_html("**bold**")
        self.assertNotIn("**", html)
        self.assertIn("<strong>bold</strong>", html)
