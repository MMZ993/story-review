"""Load the mock dataset and expand scenario-canonical expected files.

Invariants enforced here (docs-local/plans/phase-3-mock-dataset.md,
increment 4):

- every story file parses as a strict StoryEnvelope; story ids are the
  unique sequential story-01..story-42 set; the matrix covers
  6 templates x 7 scenarios exactly;
- every expected file parses as a strict ExpectedCase keyed by scenario;
- expansion pairs each story with its scenario's expected contract into a
  test case; a scenario without stories (or vice versa) is a DatasetError.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from dataset_loader.envelope import StoryEnvelope
from dataset_loader.expected import ExpectedCase

STORY_FILES_GLOB = "t?/*.json"
EXPECTED_FILES_GLOB = "*.json"


class DatasetError(Exception):
    """Raised when the dataset on disk violates its own contract."""


def load_all_stories(stories_dir: Path) -> list[StoryEnvelope]:
    """Load and validate every story file under stories_dir (t1..t6).

    Raises DatasetError on missing/invalid files, duplicate case ids or
    story ids, non-sequential story ids, or a matrix hole.
    """

    paths = sorted(stories_dir.glob(STORY_FILES_GLOB))
    stories: list[StoryEnvelope] = []
    for path in paths:
        try:
            stories.append(StoryEnvelope.model_validate_json(path.read_text()))
        except ValidationError as exc:
            raise DatasetError(f"invalid story envelope {path}: {exc}") from exc
    if not stories:
        raise DatasetError(f"no story files found under {stories_dir}")

    case_ids = [s.case_id for s in stories]
    if len(set(case_ids)) != len(case_ids):
        raise DatasetError("duplicate case ids in dataset")
    story_ids = sorted(s.story_id for s in stories)
    sequential = [f"story-{n:02d}" for n in range(1, len(stories) + 1)]
    if story_ids != sequential:
        raise DatasetError(
            "story ids must be the unique sequential set "
            f"{sequential[0]}..{sequential[-1]}"
        )
    for story in stories:
        if not story.case_id_matches_components():
            raise DatasetError(
                f"case id {story.case_id} does not match "
                f"{story.template}/{story.scenario}"
            )
        missing = story.work_item.missing_required_fields()
        if missing:
            raise DatasetError(
                f"{story.case_id}: work item missing required fields {missing}"
            )

    _validate_linked_stories(stories)
    return stories


def _validate_linked_stories(stories: list[StoryEnvelope]) -> None:
    """Every linked_stories reference must point at a dataset story file.

    Also rejects self-references — a story cannot be its own context.
    """

    known_case_ids = {s.case_id for s in stories}
    for story in stories:
        if story.case_id in story.linked_stories:
            raise DatasetError(
                f"{story.case_id}: linked_stories references itself"
            )
        unknown = set(story.linked_stories) - known_case_ids
        if unknown:
            raise DatasetError(
                f"{story.case_id}: unknown linked story {sorted(unknown)}"
            )


def load_expected(expected_dir: Path) -> dict[str, ExpectedCase]:
    """Load and validate every scenario-canonical expected file.

    Returns a scenario -> ExpectedCase mapping; raises DatasetError when a
    file's scenario key does not match its filename or on validation
    failure.
    """

    cases: dict[str, ExpectedCase] = {}
    for path in sorted(expected_dir.glob(EXPECTED_FILES_GLOB)):
        try:
            case = ExpectedCase.model_validate_json(path.read_text())
        except ValidationError as exc:
            raise DatasetError(f"invalid expected file {path}: {exc}") from exc
        if path.stem != case.scenario:
            raise DatasetError(
                f"expected file {path.name} must key scenario {case.scenario}"
            )
        cases[case.scenario] = case
    if not cases:
        raise DatasetError(f"no expected files found under {expected_dir}")
    return cases


class TestCase:
    """One runnable test case: a story paired with its scenario contract."""

    def __init__(self, story: StoryEnvelope, expected: ExpectedCase):
        self.story = story
        self.expected = expected
        self.case_id = story.case_id

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"TestCase({self.case_id})"


def expand_cases(
    stories: list[StoryEnvelope], expected: dict[str, ExpectedCase]
) -> list[TestCase]:
    """Pair every story with its scenario's expected contract.

    Raises DatasetError when a story's scenario has no expected file or an
    expected scenario has no story (both break the 1:1 scenario pairing
    that format invariance requires).
    """

    cases: list[TestCase] = []
    for story in stories:
        if story.scenario not in expected:
            raise DatasetError(
                f"story scenario {story.scenario!r} has no expected file"
            )
        cases.append(TestCase(story, expected[story.scenario]))
    orphan_scenarios = set(expected) - {c.expected.scenario for c in cases}
    if orphan_scenarios:
        raise DatasetError(
            f"expected scenarios without stories: {sorted(orphan_scenarios)}"
        )
    return cases
