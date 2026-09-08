"""Flatten Azure DevOps rich-text HTML to the design plain-text projection.

ADO `System.Description` and `Microsoft.VSTS.Common.AcceptanceCriteria` are
rich-text HTML; the shared `Text` fields are plain text. Rules (owner-approved
D10 mapping): all tags stripped, character entities decoded, block-level tags
(`</p>`, `</li>`, `<br>`, headings, list/table containers) end the current
line, inline tags (`b`, `i`, `code`, ...) keep their inner text, and runs of
whitespace collapse to a single space per line.

`html_to_text` joins the resulting lines with newlines (one `Text` value);
`html_to_blocks` returns one entry per line (list items for acceptance
criteria). Empty or blank input yields "" / []. Stdlib-only: no HTML
dependency, deterministic output.
"""

from __future__ import annotations

from html.parser import HTMLParser

#: Tags whose start/end terminates the current output line.
_BLOCK_TAGS = frozenset(
    {
        "p",
        "li",
        "br",
        "div",
        "ul",
        "ol",
        "tr",
        "table",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
    }
)


def _normalize(line: str) -> str:
    """Collapse whitespace runs and strip a single output line."""
    return " ".join(line.split())


class _LineCollector(HTMLParser):
    """Collects decoded text content as a list of stripped lines."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._current: list[str] = []

    def handle_data(self, data: str) -> None:
        self._current.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self._flush()

    def _flush(self) -> None:
        line = _normalize("".join(self._current))
        self._current = []
        if line:
            self.lines.append(line)

    def result(self) -> list[str]:
        self._flush()
        return self.lines


def _parse(html: str) -> list[str]:
    if not html:
        return []
    collector = _LineCollector()
    collector.feed(html)
    collector.close()
    return collector.result()


def html_to_text(html: str | None) -> str:
    """Flatten rich-text HTML to a single plain-text value (lines = \\n)."""
    return "\n".join(_parse(html or ""))


def html_to_blocks(html: str | None) -> list[str]:
    """Flatten rich-text HTML to one plain-text entry per block element."""
    return _parse(html or "")
