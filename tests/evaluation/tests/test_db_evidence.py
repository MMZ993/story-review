"""db_evidence pure-logic unit tests (event-content parsing, inc 1)."""

from __future__ import annotations

from evaluation.db_evidence import _tool_call_names


def test_extracts_function_call_names_in_order():
    content = {
        "parts": [
            {"text": "thinking"},
            {"function_call": {"name": "get_story", "args": {}}},
            {"function_call": {"name": "list_stories", "args": {}}},
        ]
    }
    import json

    assert _tool_call_names(json.dumps(content)) == ["get_story", "list_stories"]


def test_ignores_responses_and_plain_text():
    content = {
        "parts": [
            {"text": "hello"},
            {"function_response": {"name": "get_story", "response": {}}},
        ]
    }
    import json

    assert _tool_call_names(json.dumps(content)) == []


def test_tolerates_invalid_json():
    assert _tool_call_names("not json") == []
