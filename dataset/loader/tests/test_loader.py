"""Behavior tests for the dataset loader harness.

Contract sources:
- docs/quality/mock-data.md (expected-file contract, D9 amendment 2:
  scenario-canonical expected files expanded per case at load time)
- docs/design/schemas.md (vocabulary: TurnOutcome, SessionState,
  ArtifactType, Format; StoryId pattern)
- dataset/README.md (envelope shape, story-id scheme)

The tests run against the REAL dataset files in dataset/stories/ and
dataset/expected/ plus small in-memory fixtures for negative cases.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dataset_loader.dataset import DatasetError, expand_cases, load_all_stories, load_expected
from dataset_loader.envelope import StoryEnvelope
from dataset_loader.expected import ExpectedCase

REPO = Path(__file__).resolve().parents[3]
STORIES = REPO / "dataset" / "stories"
EXPECTED = REPO / "dataset" / "expected"

SCENARIOS = {
    "clean",
    "business-weak",
    "engineering-weak",
    "conflicting",
    "partial-resolution",
    "unresolvable",
    "hidden-conflict",
}
# t1-only comment scenarios (D9 amendment 3): continue the story-id
# sequence after the 42-story core grid, and appear ONLY in t1.
T1_ONLY_SCENARIOS = {
    "comments-benign",
    "comments-clarify-business",
    "comments-complete-engineering",
}
TEMPLATES = {f"t{i}" for i in range(1, 7)}


# ---------------------------------------------------------------- stories


def test_loads_all_45_stories_with_unique_sequential_story_ids():
    stories = load_all_stories(STORIES)
    assert len(stories) == 45
    ids = [s.story_id for s in stories]
    assert len(set(ids)) == 45
    assert set(ids) == {f"story-{n:02d}" for n in range(1, 46)}


def test_matrix_is_core_grid_plus_t1_only_comment_scenarios():
    stories = load_all_stories(STORIES)
    cells = {(s.template, s.scenario) for s in stories}
    assert cells == {(t, sc) for t in TEMPLATES for sc in SCENARIOS} | {
        ("t1", sc) for sc in T1_ONLY_SCENARIOS
    }


def test_t1_only_scenario_outside_t1_is_rejected():
    env = _envelope_fixture()
    env.update(case_id="t2/comments-benign", template="t2",
               scenario="comments-benign", story_id="story-08")
    with pytest.raises(ValidationError):
        StoryEnvelope.model_validate(env)


def test_case_id_matches_template_and_scenario():
    for story in load_all_stories(STORIES):
        assert story.case_id == f"{story.template}/{story.scenario}"


def test_every_story_file_on_disk_has_a_valid_envelope():
    files = sorted(p for p in STORIES.glob("t?/*.json"))
    assert len(files) == 45
    load_all_stories(STORIES)  # raises on any invalid envelope


# --------------------------------------------------------------- expected


def test_loads_ten_scenario_canonical_expected_files():
    expected = load_expected(EXPECTED)
    assert set(expected) == SCENARIOS | T1_ONLY_SCENARIOS


def test_expected_scenario_matches_filename():
    for path in EXPECTED.glob("*.json"):
        assert path.stem == json.loads(path.read_text())["scenario"]


def test_expected_turn_numbers_are_contiguous_from_one():
    for case in load_expected(EXPECTED).values():
        numbers = [t.turn_number for t in case.expected_turns]
        assert numbers == list(range(1, len(case.po_script) + 2))


def test_po_script_length_matches_expected_turns_minus_opening():
    for case in load_expected(EXPECTED).values():
        assert len(case.po_script) == len(case.expected_turns) - 1


def test_park_scenario_pins_the_loop_cap():
    cases = load_expected(EXPECTED)
    unresolvable = cases["unresolvable"].expected_final
    assert unresolvable.state == "parked"
    assert unresolvable.facilitator_turn_count == 10


# ------------------------------------------------------- case expansion


def test_expansion_yields_45_cases_pairing_story_and_expected():
    cases = expand_cases(load_all_stories(STORIES), load_expected(EXPECTED))
    assert len(cases) == 45
    for case in cases:
        assert case.story.case_id == case.case_id
        assert case.expected.scenario == case.story.scenario


def test_core_scenarios_cover_all_six_templates_t1_only_just_t1():
    cases = expand_cases(load_all_stories(STORIES), load_expected(EXPECTED))
    per_scenario = {}
    for case in cases:
        per_scenario.setdefault(case.expected.scenario, set()).add(
            case.story.template
        )
    for scenario in SCENARIOS:
        assert per_scenario[scenario] == TEMPLATES, scenario
    for scenario in T1_ONLY_SCENARIOS:
        assert per_scenario[scenario] == {"t1"}, scenario


# ------------------------------------------------------- negative cases


def _envelope_fixture() -> dict:
    return json.loads((STORIES / "t1" / "clean.json").read_text())


def test_envelope_missing_story_id_is_rejected():
    env = _envelope_fixture()
    del env["story_id"]
    with pytest.raises(ValidationError):
        StoryEnvelope.model_validate(env)


def test_envelope_with_malformed_story_id_is_rejected():
    env = _envelope_fixture()
    env["story_id"] = "story-1"
    with pytest.raises(ValidationError):
        StoryEnvelope.model_validate(env)


def test_envelope_without_work_item_fields_is_rejected():
    env = _envelope_fixture()
    env["work_item"] = {"id": 5}
    with pytest.raises(ValidationError):
        StoryEnvelope.model_validate(env)


def _expected_fixture() -> dict:
    return json.loads((EXPECTED / "clean.json").read_text())


def test_po_script_turn_with_both_message_and_acceptance_is_rejected():
    case = _expected_fixture()
    turn = case["po_script"][0]
    turn["message"] = "hello"
    turn["po_accepted"] = True
    with pytest.raises(ValidationError):
        ExpectedCase.model_validate(case)


def test_po_script_turn_with_neither_message_nor_acceptance_is_rejected():
    case = _expected_fixture()
    case["po_script"][0] = {}
    with pytest.raises(ValidationError):
        ExpectedCase.model_validate(case)


def test_turn_number_gap_is_rejected():
    case = _expected_fixture()
    case["expected_turns"][1]["turn_number"] = 3
    with pytest.raises(ValidationError):
        ExpectedCase.model_validate(case)


def test_state_not_matching_outcome_is_rejected():
    case = _expected_fixture()
    case["expected_turns"][0]["state_after"] = "completed"
    with pytest.raises(ValidationError):
        ExpectedCase.model_validate(case)


def test_report_artifact_on_non_finalize_turn_is_rejected():
    case = _expected_fixture()
    case["expected_turns"][0]["produced_artifacts"].append(
        {"type": "report-md", "version": 1}
    )
    with pytest.raises(ValidationError):
        ExpectedCase.model_validate(case)


def test_finding_stub_with_wrong_prefix_is_rejected():
    case = json.loads((EXPECTED / "business-weak.json").read_text())
    case["expected_findings"]["review-business"]["required"][0]["key"] = "E-1"
    with pytest.raises(ValidationError):
        ExpectedCase.model_validate(case)


def test_invoke_outside_vocabulary_is_rejected():
    case = _expected_fixture()
    case["expected_turns"][0]["delegation"]["invoke"] = "reviewer"
    with pytest.raises(ValidationError):
        ExpectedCase.model_validate(case)


def test_unresolvable_unpinned_turns_allow_partial_delegation():
    """Unresolvable turns 2-9 carry only open_issues_empty — still valid."""
    case = json.loads((EXPECTED / "unresolvable.json").read_text())
    assert case["expected_turns"][1]["delegation"] == {"open_issues_empty": False}
    ExpectedCase.model_validate(case)  # must not raise


def test_explicit_null_produced_artifacts_means_unpinned():
    """`produced_artifacts: null` marks a turn's artifact set unpinned."""
    case = json.loads((EXPECTED / "unresolvable.json").read_text())
    case["expected_turns"][1]["produced_artifacts"] = None
    parsed = ExpectedCase.model_validate(case)
    assert parsed.expected_turns[1].produced_artifacts is None
    # omission keeps the pinned-empty meaning (assert nothing produced)
    assert parsed.expected_turns[0].produced_artifacts is not None


def test_expansion_fails_when_scenario_has_no_story():
    stories = [s for s in load_all_stories(STORIES) if s.scenario != "clean"]
    with pytest.raises(DatasetError):
        expand_cases(stories, load_expected(EXPECTED))


# ------------------------------------------- further negative coverage


def test_expected_filename_not_matching_scenario_is_rejected(tmp_path):
    payload = json.loads((EXPECTED / "clean.json").read_text())
    (tmp_path / "other.json").write_text(json.dumps(payload))
    with pytest.raises(DatasetError):
        load_expected(tmp_path)


def test_duplicate_case_ids_are_rejected(tmp_path):
    story = json.loads((STORIES / "t1" / "clean.json").read_text())
    (tmp_path / "t1").mkdir()
    (tmp_path / "t1" / "a.json").write_text(json.dumps(story))
    dup = dict(story, story_id="story-02")
    (tmp_path / "t1" / "b.json").write_text(json.dumps(dup))
    with pytest.raises(DatasetError, match="duplicate case ids"):
        load_all_stories(tmp_path)


def test_non_sequential_story_ids_are_rejected(tmp_path):
    story = json.loads((STORIES / "t1" / "clean.json").read_text())
    story["story_id"] = "story-99"
    (tmp_path / "t1").mkdir()
    (tmp_path / "t1" / "a.json").write_text(json.dumps(story))
    with pytest.raises(DatasetError, match="sequential"):
        load_all_stories(tmp_path)


def test_completed_case_must_render_requested_formats():
    case = _expected_fixture()
    case["expected_final"]["reports"] = ["pdf"]
    with pytest.raises(ValidationError, match="requested report formats"):
        ExpectedCase.model_validate(case)


def test_acceptance_on_non_finalized_case_is_rejected():
    case = json.loads((EXPECTED / "unresolvable.json").read_text())
    case["expected_final"]["po_accepted"] = True
    with pytest.raises(ValidationError, match="finalize-path"):
        ExpectedCase.model_validate(case)


# ------------------------------------------- extension envelope fields


def test_envelope_accepts_comments_and_linked_stories():
    env = _envelope_fixture()
    env["comments"] = [
        {
            "text": "Which PSP is in scope?",
            "createdDate": "2026-09-07T10:00:00.000Z",
            "createdBy": {"displayName": "PO"},
        }
    ]
    env["linked_stories"] = ["t2/clean"]
    parsed = StoryEnvelope.model_validate(env)
    assert parsed.comments[0].text == "Which PSP is in scope?"
    assert parsed.linked_stories == ["t2/clean"]


def test_extension_fields_default_to_empty():
    parsed = StoryEnvelope.model_validate(_envelope_fixture())
    assert parsed.comments == []
    assert parsed.linked_stories == []


def test_comment_without_text_is_rejected():
    env = _envelope_fixture()
    env["comments"] = [{"createdDate": "2026-09-07T10:00:00.000Z"}]
    with pytest.raises(ValidationError):
        StoryEnvelope.model_validate(env)


def test_linked_stories_over_five_are_rejected():
    env = _envelope_fixture()
    env["linked_stories"] = [f"t1/clean-{n}" for n in range(6)]
    with pytest.raises(ValidationError):
        StoryEnvelope.model_validate(env)


def test_linked_stories_duplicates_are_rejected():
    env = _envelope_fixture()
    env["linked_stories"] = ["t2/clean", "t2/clean"]
    with pytest.raises(ValidationError):
        StoryEnvelope.model_validate(env)


def test_self_referencing_linked_story_is_rejected(tmp_path):
    env = _envelope_fixture()
    env["linked_stories"] = [env["case_id"]]
    _copy_dataset(tmp_path, [env])
    with pytest.raises(DatasetError, match="itself"):
        load_all_stories(tmp_path / "stories")


def test_linked_story_without_target_file_is_rejected(tmp_path):
    env = _envelope_fixture()
    env["linked_stories"] = ["t1/does-not-exist"]
    _copy_dataset(tmp_path, [env])
    with pytest.raises(DatasetError, match="unknown linked story"):
        load_all_stories(tmp_path / "stories")


def _copy_dataset(tmp_path: Path, modified: list[dict]) -> None:
    """Copy the real stories tree into tmp_path, applying envelope edits."""
    stories = tmp_path / "stories"
    edited = {(e["case_id"]): e for e in modified}
    for path in sorted(STORIES.glob("t?/*.json")):
        env = json.loads(path.read_text())
        env = edited.pop(env["case_id"], env)
        dest = stories / path.parent.name / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(env))
    assert not edited, "fixture edits reference unknown case ids"
