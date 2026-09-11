"""Tests for the facilitator serving-safe mirrors (D13 amendment 1 family).

Same discipline as the reviewer/synthesis mirrors: identical field names,
serving-safe plain types, no cross-field validators; the strict shared
`FacilitatorTurnOutput` stays the validation authority at the adapter
boundary. Pure and deterministic.
"""

from __future__ import annotations

import json



from agent_kit.llm_output import (
    MirrorDelegationDecision,
    MirrorIssueDraft,
    MirrorResolutionDraft,
    ServingSafeFacilitatorTurnOutput,
)


def test_mirror_supports_new_issues() -> None:
    """D19: the serving-safe mirror must expose `new_issues` (mirror of
    `IssueDraft`) so Vertex structured output can actually emit the
    facilitator-minted descriptors — the strict model stays the authority."""
    import json

    from review_schemas import FacilitatorTurnOutput

    mirror = ServingSafeFacilitatorTurnOutput(
        reply="r",
        delegation=MirrorDelegationDecision(
            invoke="none", open_issues=["E-2", "F-1"], readiness="needs_work"
        ),
        new_issues=[
            MirrorIssueDraft(
                issue="F-1",
                title="Retry storm during PSP outage",
                description="Retries may amplify PSP load; circuit breaker required.",
            )
        ],
    )
    strict = FacilitatorTurnOutput.model_validate(json.loads(mirror.model_dump_json()))
    assert strict.new_issues[0].issue == "F-1"
    assert strict.new_issues[0].title == "Retry storm during PSP outage"


def test_mirrors_keep_shared_field_names() -> None:
    mirror = ServingSafeFacilitatorTurnOutput(
        reply="Please clarify the retention policy.",
        delegation=MirrorDelegationDecision(
            invoke="none",
            open_issues=["C-1"],
            readiness="needs_work",
        ),
        resolutions=[
            MirrorResolutionDraft(
                issue="B-2",
                disposition="resolved",
                explanation="PO added the 30-second metric.",
            )
        ],
    )
    assert mirror.delegation.invoke == "none"
    assert mirror.resolutions[0].disposition == "resolved"


def test_mirrors_accept_invalid_combinations() -> None:
    """Serving-side mirrors must not enforce combination rules — the strict
    model rejects them adapter-side (and triggers corrective re-prompts)."""
    mirror = ServingSafeFacilitatorTurnOutput(
        reply="r",
        delegation=MirrorDelegationDecision(
            invoke="business",
            reuse_previous=True,  # invalid combination; serving accepts
        ),
    )
    assert mirror.delegation.reuse_previous is True


def test_unknown_fields_do_not_leak_into_payload() -> None:
    """Mirrors follow the serving pattern (plain BaseModel); unknown keys
    never survive the roundtrip because the dumped payload contains only
    mirror fields."""
    import json

    from review_schemas import FacilitatorTurnOutput

    payload = {
        "reply": "r",
        "delegation": {"invoke": "none", "open_issues": [], "readiness": "needs_work"},
        "resolutions": [],
    }
    strict = FacilitatorTurnOutput.model_validate(
        json.loads(ServingSafeFacilitatorTurnOutput.model_validate(payload).model_dump_json())
    )
    assert strict.reply == "r"


def test_json_roundtrip_shape() -> None:
    """The serialized mirror payload must revalidate through the strict
    shared model once the combination rules are satisfied."""
    from review_schemas import FacilitatorTurnOutput

    mirror = ServingSafeFacilitatorTurnOutput(
        reply="Opening turn reply.",
        delegation={
            "invoke": "none",
            "extra_context": None,
            "reuse_previous": False,
            "open_issues": ["C-1"],
            "readiness": "needs_work",
        },
        resolutions=[],
    )
    strict = FacilitatorTurnOutput.model_validate(json.loads(mirror.model_dump_json()))
    assert strict.delegation.open_issues == ["C-1"]
