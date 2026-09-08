"""Azure data source: live Azure DevOps REST behind the same interface (D10).

Production/demo path only — never exercised against the network by the
local suites (evaluation runs must stay on the frozen `mock` dataset).
Tests drive it through ``httpx.MockTransport`` with recorded-shape fixtures.

REST access (Runbook-09 proven): PAT basic auth against
``https://dev.azure.com/{org}``; `list_stories` = WIQL for the project's
user stories + a thin details batch; `get_story` =
``workitems/{id}?$expand=all`` + the comments API, mapped through the same
preparation core as the mock dataset (``prepare_work_item``). Parent
Feature/Epic work items are fetched on demand to build the context index;
linked work items (Related / Dependency relations) become context stories.
"""

from __future__ import annotations

import base64

import httpx

from ado_wire import WorkItem, WorkItemComment
from review_schemas.review import ContextStory, StoryDetail, StoryComment, StorySummary

from story_mcp.backlog import StoryNotFound, apply_filter, check_id_space
from story_mcp.prepare import (
    ContextIndex,
    _RELATION_BY_ADO_TYPE,
    _comments,
    context_story_from_work_item,
    prepare_work_item,
)

_API_VERSION = "7.1"

_LIST_FIELDS = "System.Id,System.Title,System.State"

_WIQL_TEMPLATE = (
    "SELECT [System.Id] FROM WorkItems "
    "WHERE [System.TeamProject] = @project "
    "AND [System.WorkItemType] = 'User Story' "
    "ORDER BY [System.Id]"
)


class SourceUnavailable(Exception):
    """The Azure DevOps REST endpoint failed or returned an unusable shape.

    Carries the HTTP status when there was one (0 = no response), so a
    missing work item (404) can be distinguished from a transient failure.
    """

    def __init__(self, message: str, *, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class AzureDevOpsRestClient:
    """Thin authenticated wrapper over the ADO REST surface we use."""

    def __init__(
        self,
        *,
        org: str,
        project: str,
        pat: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = f"https://dev.azure.com/{org}"
        self._project = project
        self._transport = transport
        self._headers = {
            "Authorization": "Basic "
            + base64.b64encode(f":{pat}".encode()).decode(),
            "Accept": "application/json",
        }

    def wiql_story_ids(self) -> list[int]:
        """All user-story work-item ids in the project, ordered by id."""
        response = self._request(
            "POST",
            f"/{self._project}/_apis/wit/wiql",
            json={"query": _WIQL_TEMPLATE},
        )
        try:
            return [entry["id"] for entry in response["workItems"]]
        except (KeyError, TypeError) as exc:
            raise SourceUnavailable(f"unexpected WIQL response shape: {exc}") from exc

    def story_summaries(self) -> list[StorySummary]:
        """Summaries for every user story (WIQL + one details batch)."""
        ids = self.wiql_story_ids()
        if not ids:
            return []
        response = self._request(
            "GET",
            f"/{self._project}/_apis/wit/workitemsbatch",
            json={"ids": ids, "fields": _LIST_FIELDS.split(",")},
        )
        summaries: list[StorySummary] = []
        for item in response.get("value", []):
            fields = item.get("fields", {})
            summaries.append(
                StorySummary(
                    story_id=f"ado-{item['id']}",
                    title=fields["System.Title"],
                    status=fields["System.State"],
                )
            )
        return summaries

    def work_item(self, item_id: int) -> WorkItem:
        """One work item with relations (``$expand=all``)."""
        response = self._request(
            "GET",
            f"/{self._project}/_apis/wit/workitems/{item_id}",
            params={"$expand": "all"},
        )
        return WorkItem.model_validate(response)

    def comments(self, item_id: int) -> list[WorkItemComment]:
        """The discussion comments of one work item, oldest first."""
        response = self._request(
            "GET", f"/{self._project}/_apis/wit/workitems/{item_id}/comments"
        )
        return [
            WorkItemComment.model_validate(entry)
            for entry in sorted(
                response.get("comments", []),
                key=lambda c: str(c.get("createdDate", "")),
            )
        ]

    def _request(self, method: str, path: str, **kwargs) -> dict:
        params = kwargs.pop("params", {}) | {"api-version": _API_VERSION}
        try:
            with httpx.Client(
                base_url=self._base_url,
                headers=self._headers,
                transport=self._transport,
                timeout=30.0,
            ) as client:
                response = client.request(method, path, params=params, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise SourceUnavailable(
                f"azure devops request failed: {exc}", status=exc.response.status_code
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceUnavailable(f"azure devops request failed: {exc}") from exc


class AzureBacklogSource:
    """Serves live Azure DevOps stories as `ado-N` ``StoryDetail`` entries."""

    def __init__(self, *, org: str, project: str, pat: str, client=None) -> None:
        self._client = client or AzureDevOpsRestClient(org=org, project=project, pat=pat)

    def list_stories(self, status_filter: str | None) -> list[StorySummary]:
        return apply_filter(self._client.story_summaries(), status_filter)

    def get_story(self, story_id: str) -> StoryDetail:
        check_id_space("azure", story_id)
        item_id = int(story_id[len("ado-") :])
        story = self._fetch_story(item_id)
        context = self._fetch_context(story)
        context_stories = self._fetch_context_stories(story)
        return prepare_work_item(
            story,
            story_id=story_id,
            comments=self._client.comments(item_id),
            context=context,
            context_stories=context_stories,
        )

    def _fetch_story(self, item_id: int) -> WorkItem:
        """Fetch the work item; only a 404 is STORY_NOT_FOUND — a transient
        failure stays UPSTREAM_UNAVAILABLE (retryable)."""
        try:
            return self._client.work_item(item_id)
        except SourceUnavailable as exc:
            if exc.status == 404:
                raise StoryNotFound(f"ado-{item_id}") from exc
            raise

    def _fetch_context(self, story: WorkItem) -> ContextIndex:
        """Parent Feature + grandparent Epic, as the context index."""
        parent_id = story.fields.get("System.Parent")
        if not isinstance(parent_id, int):
            raise SourceUnavailable(f"work item {story.id} has no parent feature")
        feature = self._client.work_item(parent_id)
        epic_id = feature.fields.get("System.Parent")
        if not isinstance(epic_id, int):
            raise SourceUnavailable(f"feature {feature.id} has no parent epic")
        epic = self._client.work_item(epic_id)
        return ContextIndex.from_items(
            [feature.model_dump(mode="json"), epic.model_dump(mode="json")]
        )

    def _fetch_context_stories(self, story: WorkItem) -> list[ContextStory]:
        """Linked work items (Related / Dependency) as context stories."""
        stories = []
        for relation in story.model_extra.get("relations") or []:
            rel = relation.get("rel")
            if rel not in _RELATION_BY_ADO_TYPE:
                continue
            target_id = int(str(relation.get("url", "")).rstrip("/").rsplit("/", 1)[-1])
            target = self._client.work_item(target_id)
            stories.append(
                context_story_from_work_item(
                    target,
                    _comments(self._client.comments(target_id)),
                    _RELATION_BY_ADO_TYPE[rel],
                    story_id=f"ado-{target_id}",
                )
            )
        return stories
