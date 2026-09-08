"""Behavior tests for the ADO wire models moved to ``ado_wire``.

Covers validation behavior of ``WorkItem`` and ``WorkItemComment``
(verbatim Azure DevOps work-item / comment shapes), not implementation
details. Mirrors the guarantees the dataset envelope and the story-MCP
preparation step rely on.
"""

from __future__ import annotations

import pytest

from ado_wire import WorkItem, WorkItemComment


def _minimal_work_item() -> dict:
    return {
        "id": 42,
        "fields": {
            "System.Title": "Fix login",
            "System.WorkItemType": "User Story",
            "System.AreaPath": "Demo\\Portal",
            "System.State": "New",
        },
    }


class TestWorkItem:
    def test_minimal_work_item_validates(self):
        wi = WorkItem.model_validate(_minimal_work_item())
        assert wi.id == 42
        assert wi.fields["System.Title"] == "Fix login"
        assert wi.missing_required_fields() == ()

    def test_extra_fields_and_keys_are_kept_verbatim(self):
        payload = _minimal_work_item()
        payload["fields"]["Custom.Field"] = "kept"
        payload["relations"] = [{"rel": "System.LinkTypes.Related", "url": "x/1"}]
        wi = WorkItem.model_validate(payload)
        assert wi.fields["Custom.Field"] == "kept"
        assert wi.model_extra["relations"][0]["rel"] == "System.LinkTypes.Related"

    def test_missing_required_fields_reports_all_missing(self):
        wi = WorkItem.model_validate(
            {"id": 1, "fields": {"System.Title": "only", "System.State": ""}}
        )
        assert wi.missing_required_fields() == (
            "System.WorkItemType",
            "System.AreaPath",
            "System.State",
        )

    def test_work_item_without_id_is_rejected(self):
        item = _minimal_work_item()
        del item["id"]
        with pytest.raises(Exception):
            WorkItem.model_validate(item)


class TestWorkItemComment:
    def test_comment_with_text_validates_and_keeps_extras(self):
        comment = WorkItemComment.model_validate(
            {
                "text": "Please clarify the acceptance criteria.",
                "createdBy": {"displayName": "Ada"},
                "createdDate": "2025-01-02T10:00:00Z",
            }
        )
        assert comment.text == "Please clarify the acceptance criteria."
        assert comment.model_extra["createdBy"]["displayName"] == "Ada"

    def test_empty_comment_text_is_rejected(self):
        with pytest.raises(Exception):
            WorkItemComment.model_validate({"text": ""})

    def test_comment_without_text_is_rejected(self):
        with pytest.raises(Exception):
            WorkItemComment.model_validate({"createdBy": {"displayName": "Ada"}})
