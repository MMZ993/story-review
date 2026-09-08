"""Behavior tests for the backlog core: id spaces, filter, source resolution.

D10: mock (`story-NN`) and azure (`ado-N`) id spaces never mix; cross-source
lookups are `STORY_NOT_FOUND`. `list_stories` filter is a case-insensitive
substring match on the story status.
"""

from __future__ import annotations

import pytest

from review_schemas.review import StorySummary

from story_mcp.backlog import (
    AZURE_ID_PATTERN,
    MOCK_ID_PATTERN,
    InvalidSourceOverride,
    StoryNotFound,
    apply_filter,
    check_id_space,
    resolve_source,
)


def _summary(story_id: str, status: str = "New") -> StorySummary:
    return StorySummary(story_id=story_id, title="t", status=status)


class TestIdSpaces:
    def test_mock_accepts_story_ids_and_rejects_ado_ids(self):
        check_id_space("mock", "story-01")
        with pytest.raises(StoryNotFound):
            check_id_space("mock", "ado-5")

    def test_azure_accepts_ado_ids_and_rejects_story_ids(self):
        check_id_space("azure", "ado-5")
        with pytest.raises(StoryNotFound):
            check_id_space("azure", "story-01")

    def test_ado_ids_up_to_8_digits(self):
        check_id_space("azure", "ado-12345678")

    def test_patterns_pin_the_two_id_spaces(self):
        assert MOCK_ID_PATTERN.fullmatch("story-42")
        assert not MOCK_ID_PATTERN.fullmatch("story-1")
        assert AZURE_ID_PATTERN.fullmatch("ado-99999999")
        assert not AZURE_ID_PATTERN.fullmatch("ado-123456789")


class TestApplyFilter:
    def test_no_filter_returns_all(self):
        stories = [_summary("story-01"), _summary("story-02")]
        assert apply_filter(stories, None) == stories

    def test_filter_matches_status_substring_case_insensitive(self):
        stories = [_summary("story-01", "New"), _summary("story-02", "Resolved")]
        assert apply_filter(stories, "new") == [stories[0]]
        assert apply_filter(stories, "res") == [stories[1]]

    def test_filter_with_no_match_returns_empty(self):
        assert apply_filter([_summary("story-01")], "closed") == []


class TestResolveSource:
    def test_none_means_deployment_default(self):
        assert resolve_source(None, "mock") == "mock"
        assert resolve_source(None, "azure") == "azure"

    def test_explicit_override_wins(self):
        assert resolve_source("azure", "mock") == "azure"

    def test_invalid_default_raises(self):
        with pytest.raises(InvalidSourceOverride):
            resolve_source(None, "bogus")
