"""Tests for the facilitator adapter core (session-scoped, corrective
re-prompts, lineage-scoped tool guard).

The frozen facilitator contract: session-scoped turn runs against the ADK
session service, at most two corrective re-prompts on malformed delegation
output, `DELEGATION_VALIDATION` on exhaustion, and adapter-side tool
argument validation (story id space; artifact reads within the supplied
lineage). The model I/O boundary is injected as a `send` callable so these
tests stay deterministic — no LLM, no MCP servers.
"""

from __future__ import annotations

import asyncio

import json

import pytest
from pydantic import ValidationError

from agent_kit.facilitator_adapter import (
    CORRECTIVE_MAX,
    DelegationValidationError,
    lineage_tool_guard,
    turn_with_corrections,
)
from agent_kit.facilitator_input import (
    FacilitatorRequest,
    FacilitatorTurnInvalid,
    render_facilitator_message,
    validate_turn_output,
)

from tests.test_facilitator_input import request, turn_output


class ScriptedModel:
    """Stands in for the session-scoped ADK run: returns queued replies."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.sent: list[str] = []

    async def __call__(self, message: str) -> str:
        self.sent.append(message)
        return self.replies.pop(0)


def valid_payload(invoke: str = "none") -> dict:
    return {
        "reply": "Here is the synthesis.",
        "delegation": {
            "invoke": invoke,
            "extra_context": None,
            "reuse_previous": False,
            "open_issues": ["C-1"],
            "readiness": "needs_work",
        },
        "resolutions": [],
    }


class TestTurnWithCorrections:
    def test_valid_first_try_no_reprompts(self) -> None:
        asyncio.run(self._test_valid_first_try_no_reprompts_async())

    async def _test_valid_first_try_no_reprompts_async(self) -> None:
        model = ScriptedModel(json.dumps(valid_payload()))
        output, corrections = await turn_with_corrections(model, request())
        assert corrections == 0
        assert output.delegation.open_issues == ["C-1"]
        assert len(model.sent) == 1

    def test_invalid_then_valid_counts_one_reprompt(self) -> None:
        asyncio.run(self._test_invalid_then_valid_counts_one_reprompt_async())

    async def _test_invalid_then_valid_counts_one_reprompt_async(self) -> None:
        bad = valid_payload()
        bad["delegation"]["invoke"] = "engineering"  # opening-turn violation
        model = ScriptedModel(json.dumps(bad), json.dumps(valid_payload()))
        output, corrections = await turn_with_corrections(model, request())
        assert corrections == 1
        assert output.delegation.invoke == "none"
        assert "opening turn" in model.sent[1]

    def test_not_json_is_also_corrected(self) -> None:
        asyncio.run(self._test_not_json_is_also_corrected_async())

    async def _test_not_json_is_also_corrected_async(self) -> None:
        model = ScriptedModel("I will help!", json.dumps(valid_payload()))
        _, corrections = await turn_with_corrections(model, request())
        assert corrections == 1
        assert "JSON" in model.sent[1] or "json" in model.sent[1]

    def test_schema_violation_is_corrected(self) -> None:
        asyncio.run(self._test_schema_violation_is_corrected_async())

    async def _test_schema_violation_is_corrected_async(self) -> None:
        bad = valid_payload()
        bad["delegation"]["extra_context"] = "no reviewer invoked"  # requires invocation
        model = ScriptedModel(json.dumps(bad), json.dumps(valid_payload()))
        _, corrections = await turn_with_corrections(model, request())
        assert corrections == 1

    def test_exhaustion_raises_delegation_validation(self) -> None:
        asyncio.run(self._test_exhaustion_raises_delegation_validation_async())

    async def _test_exhaustion_raises_delegation_validation_async(self) -> None:
        model = ScriptedModel(*(["garbage"] * (CORRECTIVE_MAX + 1)))
        with pytest.raises(DelegationValidationError, match="corrective"):
            await turn_with_corrections(model, request())
        # initial attempt + at most CORRECTIVE_MAX re-prompts
        assert len(model.sent) == CORRECTIVE_MAX + 1

    def test_invalid_then_two_more_bad_then_raise(self) -> None:
        asyncio.run(self._test_invalid_then_two_more_bad_then_raise_async())

    async def _test_invalid_then_two_more_bad_then_raise_async(self) -> None:
        bad = valid_payload()
        bad["delegation"]["invoke"] = "both"
        model = ScriptedModel(*([json.dumps(bad)] * (CORRECTIVE_MAX + 1)))
        with pytest.raises(DelegationValidationError):
            await turn_with_corrections(model, request())
        assert len(model.sent) == CORRECTIVE_MAX + 1


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class TestLineageToolGuard:
    def test_get_artifact_missing_run_rejected(self) -> None:
        result = lineage_tool_guard(FakeTool("get_artifact"), {"artifact_id": None}, request())
        assert result is not None

    def test_get_artifact_synthesis_reference_allowed(self) -> None:
        req = request()
        assert (
            lineage_tool_guard(
                FakeTool("get_artifact"),
                {
                    "artifact_id": req.synthesis_reference.artifact_id,
                    "story_run_id": req.story_run_id,
                },
                req,
            )
            is None
        )

    def test_get_story_matching_pattern_allowed(self) -> None:
        req = request()
        assert lineage_tool_guard(FakeTool("get_story"), {"story_id": req.story_id}, req) is None

    def test_get_story_bad_id_space_rejected(self) -> None:
        result = lineage_tool_guard(FakeTool("get_story"), {"story_id": "story-99; rm -rf"}, request())
        assert result is not None and "story" in result["error"].lower()

    def test_get_story_source_override_rejected(self) -> None:
        result = lineage_tool_guard(
            FakeTool("get_story"), {"story_id": "story-05", "source": "azure"}, request()
        )
        assert result is not None and "source" in result["error"]

    def test_list_stories_allowed(self) -> None:
        assert lineage_tool_guard(FakeTool("list_stories"), {}, request()) is None

    def test_get_artifact_within_lineage_allowed(self) -> None:
        req = request()
        ref = req.evidence_references[0]
        assert (
            lineage_tool_guard(
                FakeTool("get_artifact"),
                {"artifact_id": ref.artifact_id, "story_run_id": req.story_run_id},
                req,
            )
            is None
        )

    def test_get_artifact_outside_lineage_rejected(self) -> None:
        req = request()
        result = lineage_tool_guard(
            FakeTool("get_artifact"),
            {
                "artifact_id": "art-00000000-0000-0000-0000-00000000dead",
                "story_run_id": req.story_run_id,
            },
            req,
        )
        assert result is not None and "lineage" in result["error"]

    def test_get_artifact_wrong_run_rejected(self) -> None:
        req = request()
        ref = req.evidence_references[0]
        result = lineage_tool_guard(
            FakeTool("get_artifact"),
            {
                "artifact_id": ref.artifact_id,
                "story_run_id": "run-00000000-0000-0000-0000-000000000002",
            },
            req,
        )
        assert result is not None

    def test_list_artifacts_scoped_to_run_allowed(self) -> None:
        req = request()
        assert (
            lineage_tool_guard(FakeTool("list_artifacts"), {"story_run_id": req.story_run_id}, req)
            is None
        )

    def test_list_artifacts_other_run_rejected(self) -> None:
        result = lineage_tool_guard(
            FakeTool("list_artifacts"),
            {"story_run_id": "run-00000000-0000-0000-0000-000000000002"},
            request(),
        )
        assert result is not None

    def test_unknown_tool_rejected(self) -> None:
        result = lineage_tool_guard(FakeTool("save_artifact"), {}, request())
        assert result is not None

    def test_no_request_context_rejects(self) -> None:
        result = lineage_tool_guard(FakeTool("get_story"), {"story_id": "story-05"}, None)
        assert result is not None
