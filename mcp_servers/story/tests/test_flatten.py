"""Tests for the ADO rich-text HTML flattener (story_mcp.flatten).

The dataset's `System.Description` / `AcceptanceCriteria` fields are ADO
rich-text HTML; the design `Text` projection is plain text. Rules under test
(owner-approved mapping, D10): tags stripped, entities decoded, block tags
become line/item boundaries, inline tags keep their inner text, whitespace
runs collapse per line.
"""

from __future__ import annotations

import pytest

from story_mcp.flatten import html_to_blocks, html_to_text


class TestHtmlToText:
    def test_inline_tags_stripped_but_inner_text_kept(self):
        assert (
            html_to_text("<p><b>Context:</b> use <code>GET /orders/{id}</code></p>")
            == "Context: use GET /orders/{id}"
        )

    def test_entities_are_decoded(self):
        assert html_to_text("<p>a &amp; b &lt;c&gt; &quot;d&quot;</p>") == 'a & b <c> "d"'

    def test_block_tags_become_newlines(self):
        assert (
            html_to_text("<p>one</p><p>two</p>")
            == "one\ntwo"
        )

    def test_li_and_br_break_lines(self):
        assert html_to_text("<ul><li>a</li><li>b</li></ul>c<br>d") == "a\nb\nc\nd"

    def test_whitespace_runs_collapse_per_line(self):
        assert html_to_text("<p>  a   b  </p><p>\n\n c \t d </p>") == "a b\nc d"

    def test_empty_and_none_input(self):
        assert html_to_text("") == ""
        assert html_to_text(None) == ""
        assert html_to_text("   <p> </p>  ") == ""


class TestHtmlToBlocks:
    def test_each_li_is_one_block(self):
        assert html_to_blocks("<ul><li>a </li><li>b</li></ul>") == ["a", "b"]

    def test_each_p_is_one_block(self):
        assert html_to_blocks("<p>a</p><p>b</p>") == ["a", "b"]

    def test_plain_text_is_one_block(self):
        assert html_to_blocks("just text") == ["just text"]

    def test_empty_input_yields_no_blocks(self):
        assert html_to_blocks("") == []
        assert html_to_blocks("<p> </p>") == []

    def test_inline_markup_stays_inside_the_block(self):
        assert html_to_blocks("<li>x <b>y</b> &amp; z</li>") == ["x y & z"]
