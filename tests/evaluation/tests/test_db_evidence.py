"""db_evidence pure-logic unit tests (event-content parsing, inc 1)."""

from __future__ import annotations

import asyncio
import json

from evaluation.db_evidence import (
    _discover_events_columns,
    _payload_column,
    _rows_to_tool_names,
    _tool_call_names,
)



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


def test_event_data_blob_nests_content_parts():
    """ADK's `events` table stores payloads in `event_data` (jsonb) with
    the parts nested under an inner `content` object (evaluation gate
    2026-09-15: `no ADK events table found`)."""
    blob = {
        "id": "x",
        "author": "facilitator",
        "content": {
            "role": "model",
            "parts": [
                {"thought_signature": "sig"},
                {"function_call": {"name": "get_story", "args": {}}},
            ],
        },
    }
    assert _tool_call_names(json.dumps(blob)) == ["get_story"]


class _FakeConn:
    """information_schema fetch stand-in (list of plain dicts)."""

    def __init__(self, rows):
        self._rows = rows

    async def fetch(self, _sql):
        return self._rows


def test_discovery_accepts_event_data_column():
    """The events table qualifies with `event_data` in place of `content`."""
    rows = [
        {"table_name": "sessions", "column_name": "id"},
        {"table_name": "events", "column_name": "session_id"},
        {"table_name": "events", "column_name": "event_data"},
        {"table_name": "events", "column_name": "timestamp"},
    ]
    table, columns = asyncio.run(_discover_events_columns(_FakeConn(rows)))
    assert table == "events"
    assert "event_data" in columns


def test_discovery_prefers_exact_events_name_with_content():
    rows = [
        {"table_name": "event_log", "column_name": "session_id"},
        {"table_name": "event_log", "column_name": "content"},
        {"table_name": "events", "column_name": "session_id"},
        {"table_name": "events", "column_name": "content"},
    ]
    table, _ = asyncio.run(_discover_events_columns(_FakeConn(rows)))
    assert table == "events"


def test_discovery_rejects_unrelated_tables():
    rows = [
        {"table_name": "sessions", "column_name": "session_id"},
        {"table_name": "app_states", "column_name": "content"},
    ]
    try:
        asyncio.run(_discover_events_columns(_FakeConn(rows)))
    except RuntimeError as exc:
        assert "no ADK events table found" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_rows_decode_under_the_discovered_payload_column():
    """Row cells are keyed by the payload column actually selected
    (gate rerun 2026-09-15: KeyError 'content' on event_data tables)."""
    assert _payload_column(["session_id", "event_data"]) == "event_data"
    assert _payload_column(["session_id", "content", "event_data"]) == "content"
    jsonb_cell = {
        "event_data": {
            "content": {"parts": [{"function_call": {"name": "get_story"}}]}
        }
    }
    assert _rows_to_tool_names([jsonb_cell], "event_data") == ["get_story"]
