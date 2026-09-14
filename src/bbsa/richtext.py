"""Markdown → the restricted HTML that bugbounty.sa's report fields store.

The platform's report body fields are rich text, not Markdown: the web UI edits
them in a Quill editor and renders whatever HTML is stored, so raw Markdown
posted through the API shows up as literal ``**asterisks**``. This converts the
Markdown people actually write into the tag subset that Quill's own toolbar
emits (h3/h4, strong/em/s/code, pre.ql-syntax, blockquote, ol/ul/li, a), which
keeps a CLI-submitted report editable in the web editor without mangling.

Toolbar (from the live bundle): header 3/4, bold, underline, strike,
blockquote, code-block, ordered/bullet list, align, color, image, link.
"""

from __future__ import annotations

import html
import re

__all__ = ["to_html", "MAX_LEN"]

# The web editor counts the stored HTML string, not the visible text.
MAX_LEN = 5000

_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_BOLD_ALT = re.compile(r"(?<!\w)__(.+?)__(?!\w)", re.S)
_STRIKE = re.compile(r"~~(.+?)~~", re.S)
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", re.S)
_ITALIC_ALT = re.compile(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", re.S)

_HEADING = re.compile(r"(#{1,6})\s+(.*)")
_BULLET = re.compile(r"[-*+]\s+(.*)")
_NUMBER = re.compile(r"\d+[.)]\s+(.*)")
_RULE = re.compile(r"^([-*_])\1{2,}$")


def _inline(line: str) -> str:
    """Inline spans. Code spans are pulled out first (their contents stay
    literal), emphasis runs over the whole remaining line — so a **bold** or
    *italic* run may span across a `code` span — then the code spans are
    restored. Everything else is escaped so user angle brackets never markup."""
    codes: list[str] = []

    def _stash(match: re.Match) -> str:
        codes.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"  # placeholder survives html.escape

    line = re.sub(r"`([^`]+)`", _stash, line)
    line = html.escape(line)
    line = _LINK.sub(r'<a href="\2" target="_blank">\1</a>', line)
    line = _BOLD.sub(r"<strong>\1</strong>", line)
    line = _BOLD_ALT.sub(r"<strong>\1</strong>", line)
    line = _STRIKE.sub(r"<s>\1</s>", line)
    line = _ITALIC.sub(r"<em>\1</em>", line)
    line = _ITALIC_ALT.sub(r"<em>\1</em>", line)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], line)


def to_html(markdown: str) -> str:
    """Convert basic Markdown to Quill-flavoured HTML."""
    lines = str(markdown or "").replace("\r\n", "\n").split("\n")
    blocks: list[str] = []
    para: list[str] = []
    i = 0

    def flush() -> None:
        if para:
            blocks.append("<p>" + "<br>".join(_inline(x) for x in para) + "</p>")
            para.clear()

    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("```"):
            flush()
            i += 1
            body: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1  # closing fence (or EOF)
            blocks.append(
                '<pre class="ql-syntax" spellcheck="false">'
                + html.escape("\n".join(body))
                + "</pre>"
            )
            continue

        if not stripped or _RULE.match(stripped):
            flush()  # blank lines separate paragraphs; rules have no Quill format
            i += 1
            continue

        heading = _HEADING.fullmatch(stripped)
        if heading:
            flush()
            # Quill offers only h3/h4, so the whole Markdown range folds into them.
            tag = "h3" if len(heading.group(1)) <= 2 else "h4"
            blocks.append(f"<{tag}>{_inline(heading.group(2))}</{tag}>")
            i += 1
            continue

        if stripped.startswith(">"):
            flush()
            quoted: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quoted.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append(
                "<blockquote>" + "<br>".join(_inline(x) for x in quoted) + "</blockquote>"
            )
            continue

        bullet = _BULLET.fullmatch(stripped)
        number = None if bullet else _NUMBER.fullmatch(stripped)
        if bullet or number:
            flush()
            tag, pattern = ("ul", _BULLET) if bullet else ("ol", _NUMBER)
            items: list[str] = []
            # ponytail: nested lists flatten to one level; Quill marks nesting with
            # ql-indent-N classes on <li> — add if anyone actually nests.
            while i < len(lines):
                item = pattern.fullmatch(lines[i].strip())
                if not item:
                    break
                items.append(item.group(1))
                i += 1
            blocks.append(
                f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>"
            )
            continue

        para.append(stripped)
        i += 1

    flush()
    return "".join(blocks)


def demo() -> None:
    assert to_html("**bold** and *it*") == "<p><strong>bold</strong> and <em>it</em></p>"
    assert to_html("# T\n## S") == "<h3>T</h3><h3>S</h3>"
    assert to_html("### deep") == "<h4>deep</h4>"
    assert to_html("- a\n- b") == "<ul><li>a</li><li>b</li></ul>"
    assert to_html("1. a\n2. b") == "<ol><li>a</li><li>b</li></ol>"
    assert to_html("> quoted") == "<blockquote>quoted</blockquote>"
    assert to_html("`<script>`") == "<p><code>&lt;script&gt;</code></p>"
    assert to_html("**wraps `code` span**") == (
        "<p><strong>wraps <code>code</code> span</strong></p>"
    ), to_html("**wraps `code` span**")
    assert to_html("a <b> c") == "<p>a &lt;b&gt; c</p>", to_html("a <b> c")
    assert to_html("```\n<x>\n```") == (
        '<pre class="ql-syntax" spellcheck="false">&lt;x&gt;</pre>'
    )
    assert to_html("[x](http://a.b?q=1&r=2)") == (
        '<p><a href="http://a.b?q=1&amp;r=2" target="_blank">x</a></p>'
    )
    assert to_html("~~gone~~") == "<p><s>gone</s></p>"
    assert to_html("one\ntwo\n\nthree") == "<p>one<br>two</p><p>three</p>"
    assert to_html("") == ""
    assert to_html("a\n---\nb") == "<p>a</p><p>b</p>"
    print("richtext ok")


if __name__ == "__main__":
    demo()
