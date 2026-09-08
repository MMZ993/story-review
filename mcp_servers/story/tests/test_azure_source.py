"""Fixture tests for the azure data source (no network, D10).

Drives ``AzureBacklogSource`` through ``httpx.MockTransport`` with
recorded-shape ADO REST fixtures: WIQL, workitemsbatch, work item
`$expand=all`, and the comments API. Verifies URL/auth construction, the
`ado-N` id space, preparation through the shared core, and the
`UPSTREAM_UNAVAILABLE` behavior on transport failure.
"""

from __future__ import annotations

import json

import httpx
import pytest

from story_mcp.azure_source import AzureBacklogSource, SourceUnavailable
from story_mcp.backlog import StoryNotFound


def _work_item(item_id: int, fields: dict, relations: list | None = None) -> dict:
    payload = {"id": item_id, "fields": fields}
    if relations is not None:
        payload["relations"] = relations
    return payload


def _minimal_fields(title: str, *, parent: int | None = None) -> dict:
    fields = {
        "System.Title": title,
        "System.WorkItemType": "User Story",
        "System.AreaPath": "story-review\\T1",
        "System.State": "New",
        "System.Description": f"<div>{title} description</div>",
    }
    if parent is not None:
        fields["System.Parent"] = parent
    return fields


STORY = _work_item(10, _minimal_fields("Live story", parent=3))
FEATURE = _work_item(3, {"System.Title": "Feature X", "System.Parent": 2})
EPIC = _work_item(2, {"System.Title": "Epic Y", "System.Description": "<div>Roadmap</div>"})
LINKED = _work_item(77, _minimal_fields("Linked story", parent=3))
STORY_WITH_LINK = _work_item(
    10,
    _minimal_fields("Live story", parent=3),
    relations=[
        {
            "rel": "System.LinkTypes.Related",
            "url": "https://dev.azure.com/org/1234/_apis/wit/workItems/77",
        }
    ],
)


def _route(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    assert str(request.url).startswith("https://dev.azure.com/the-org/")
    assert request.headers["Authorization"].startswith("Basic ")
    if path.endswith("/wiql"):
        return httpx.Response(200, json={"workItems": [{"id": 10}]})
    if path.endswith("/workitemsbatch"):
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": 10,
                        "fields": {
                            "System.Id": 10,
                            "System.Title": "Live story",
                            "System.State": "New",
                        },
                    }
                ]
            },
        )
    if "/workitems/10/comments" in path:
        return httpx.Response(
            200,
            json={
                "totalCount": 1,
                "comments": [
                    {
                        "text": "A comment",
                        "createdBy": {"displayName": "PO"},
                        "createdDate": "2026-09-01T10:00:00Z",
                    }
                ],
            },
        )
    if "/workitems/77" in path:
        return httpx.Response(200, json=LINKED)
    if "/workitems/3" in path:
        return httpx.Response(200, json=FEATURE)
    if "/workitems/2" in path:
        return httpx.Response(200, json=EPIC)
    if "/workitems/10" in path:
        return httpx.Response(200, json=STORY)
    return httpx.Response(404, json={"message": f"unexpected path {path}"})


def _source_with_transport(transport: httpx.MockTransport) -> AzureBacklogSource:
    from story_mcp.azure_source import AzureDevOpsRestClient

    client = AzureDevOpsRestClient(
        org="the-org", project="proj", pat="pat-token", transport=transport
    )
    return AzureBacklogSource(org="the-org", project="proj", pat="pat-token", client=client)


def test_list_stories_wiql_and_batch():
    source = _source_with_transport(httpx.MockTransport(_route))
    summaries = source.list_stories(None)
    assert [s.story_id for s in summaries] == ["ado-10"]
    assert summaries[0].title == "Live story"


def test_get_story_prepares_through_shared_core():
    source = _source_with_transport(httpx.MockTransport(_route))
    detail = source.get_story("ado-10")
    assert detail.story_id == "ado-10"
    assert detail.title == "Live story"
    assert detail.epic_context.startswith("Epic Y — Feature X")
    assert detail.roadmap_context == "Roadmap"
    assert [c.text for c in detail.comments] == ["A comment"]
    assert detail.comments[0].author == "PO"


def test_story_without_relations_has_no_context_stories():
    source = _source_with_transport(httpx.MockTransport(_route))
    detail = source.get_story("ado-10")
    # fixture STORY has no relations: context stories stay empty
    assert detail.context_stories == []


def test_related_relation_becomes_context_story():
    def route(request: httpx.Request) -> httpx.Response:
        if "/workitems/10" in request.url.path and not request.url.path.endswith("/comments"):
            return httpx.Response(200, json=STORY_WITH_LINK)
        return _route(request)

    source = _source_with_transport(httpx.MockTransport(route))
    detail = source.get_story("ado-10")
    (context,) = detail.context_stories
    assert context.story_id == "ado-77"
    assert context.relation == "related"
    assert context.title == "Linked story"


def test_story_id_outside_ado_space_is_story_not_found():
    source = _source_with_transport(httpx.MockTransport(_route))
    with pytest.raises(StoryNotFound):
        source.get_story("story-01")


def test_missing_work_item_is_story_not_found():
    def route(request: httpx.Request) -> httpx.Response:
        if "/workitems/99" in request.url.path:
            return httpx.Response(404, json={"message": "not found"})
        return _route(request)

    source = _source_with_transport(httpx.MockTransport(route))
    with pytest.raises(StoryNotFound):
        source.get_story("ado-99")


def test_transient_server_error_stays_source_unavailable():
    """A 503 (or timeout) must not masquerade as STORY_NOT_FOUND."""

    def route(request: httpx.Request) -> httpx.Response:
        if "/workitems/99" in request.url.path:
            return httpx.Response(503, json={"message": "overloaded"})
        return _route(request)

    source = _source_with_transport(httpx.MockTransport(route))
    with pytest.raises(SourceUnavailable) as excinfo:
        source.get_story("ado-99")
    assert excinfo.value.status == 503


def test_transport_failure_is_source_unavailable():
    def route(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    source = _source_with_transport(httpx.MockTransport(route))
    with pytest.raises(SourceUnavailable):
        source.list_stories(None)
