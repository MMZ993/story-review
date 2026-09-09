"""Story-server contract over the compose wire: tool matrix, mock dataset
serving, and the error taxonomy as it actually crosses HTTP."""

from __future__ import annotations

from conftest import (
    ARTIFACT_URL,
    REPORT_URL,
    STORY_URL,
    call_tool,
    error,
    list_tools,
    payload,
)


def test_story_tool_matrix():
    tools = {t.name: t for t in list_tools(STORY_URL)}
    assert set(tools) == {"list_stories", "get_story"}


def test_artifact_tool_matrix():
    tools = {t.name: t for t in list_tools(ARTIFACT_URL)}
    assert set(tools) == {"save_artifact", "get_artifact", "list_artifacts"}


def test_report_tool_matrix():
    tools = {t.name: t for t in list_tools(REPORT_URL)}
    assert set(tools) == {"render_report"}


def test_list_stories_serves_full_dataset():
    result = call_tool(STORY_URL, "list_stories", {})
    summaries = payload(result)["stories"]
    assert len(summaries) == 45
    ids = {s["story_id"] for s in summaries}
    assert "story-01" in ids


def test_get_story_returns_prepared_detail():
    result = call_tool(STORY_URL, "get_story", {"story_id": "story-01"})
    detail = payload(result)
    assert detail["story_id"] == "story-01"
    assert detail["title"]


def test_cross_source_id_is_story_not_found():
    result = call_tool(STORY_URL, "get_story", {"story_id": "ado-5"})
    assert error(result)["code"] == "STORY_NOT_FOUND"
    assert error(result)["retryable"] is False


def test_unknown_story_is_story_not_found():
    result = call_tool(STORY_URL, "get_story", {"story_id": "story-99"})
    assert error(result)["code"] == "STORY_NOT_FOUND"


def test_invalid_story_id_is_validation_error():
    result = call_tool(STORY_URL, "get_story", {"story_id": "story-1"})
    assert error(result)["code"] == "VALIDATION_ERROR"


def test_unknown_field_is_validation_error():
    result = call_tool(STORY_URL, "get_story", {"story_id": "story-01", "bogus": 1})
    assert error(result)["code"] == "VALIDATION_ERROR"


def test_status_filter_narrows():
    # All 45 stories are status "New" in the frozen dataset, so a match
    # returns everything and a miss returns nothing.
    result = call_tool(STORY_URL, "list_stories", {"filter": "New"})
    assert len(payload(result)["stories"]) == 45
    result = call_tool(STORY_URL, "list_stories", {"filter": "nonexistent-status"})
    assert payload(result)["stories"] == []
