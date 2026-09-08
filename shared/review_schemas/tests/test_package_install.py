"""Mechanical export-list and package install/import tests.

1. The public export list must equal the full set of shared names declared by
   docs/design/schemas.md (mechanical diff target), with `ArtifactRecord`
   deliberately internal.
2. The package must install by local path from its locked requirements into a
   clean virtual environment and import its public API from outside the
   repository working directory.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import review_schemas

#: Every shared name docs/design/schemas.md declares for consumers, in spec
#: order (base, errors, domain, api, records, mcp). `ArtifactRecord` is not
#: here on purpose: it stays internal to the persistence layer.
EXPECTED_EXPORTS = [
    # base
    "AgentRunId", "ArtifactId", "ArtifactType", "CorrelationId", "Format",
    "HttpsUrl", "IdempotencyKey", "LeaseToken", "Perspective", "RecordState",
    "RunId", "SaveArtifactType", "SessionId", "SessionState", "Sha256",
    "ShortText", "StoryId", "StrictModel", "Text", "TurnOutcome", "UtcDatetime",
    # errors
    "ErrorBody", "ErrorCode", "ErrorEnvelope", "ToolError",
    # review
    "ContextStory", "Finding", "ReviewReport", "StoryComment", "StoryDetail",
    "StorySummary",
    # synthesis
    "ArtifactReference", "ConflictItem", "SynthesisReport",
    # facilitator
    "ConversationSummary", "DelegationDecision", "FacilitatorTurnOutput",
    "FinalizedReview", "ResolutionDraft", "ResolutionItem",
    # judge
    "JudgeDimensionScore", "JudgeIssue", "JudgeResult",
    # api
    "CanonicalOperationResult", "CanonicalReportResult", "CanonicalTurnResult",
    "CreateSessionRequest", "CreateSessionResponse", "FinalizeRequest",
    "HealthDependency", "HealthResponse", "ListSessionsQuery",
    "ListSessionsResponse", "ListStoriesQuery", "ListStoriesResponse",
    "ReportDownload", "ReportResponse", "SessionDetail", "SessionSummary",
    "TurnRequest", "TurnResponse", "TurnView",
    # records
    "AgentRunRecord", "SessionRecord", "StoryRunRecord", "TurnLeaseRecord",
    "TurnRecord",
    # mcp
    "GetArtifactInput", "GetArtifactOutput", "GetStoryInput",
    "ListArtifactsInput", "ListArtifactsOutput", "ListStoriesInput",
    "ListStoriesOutput", "RenderReportInput", "RenderReportOutput",
    "SaveArtifactInput", "SaveArtifactOutput",
]

PACKAGE_DIR = Path(__file__).resolve().parents[1]


class TestPublicExports:
    def test_all_equals_spec_names_exactly(self):
        assert list(review_schemas.__all__) == EXPECTED_EXPORTS

    def test_artifact_record_stays_internal(self):
        assert "ArtifactRecord" not in review_schemas.__all__
        assert not hasattr(review_schemas, "ArtifactRecord")

    def test_every_export_is_importable(self):
        for name in review_schemas.__all__:
            assert getattr(review_schemas, name, None) is not None, name


class TestPackageInstall:
    def test_path_install_imports_outside_working_directory(self):
        """Install into a fresh venv from the locked requirements and import
        the public API with the venv interpreter from a neutral cwd."""
        with tempfile.TemporaryDirectory(prefix="review-schemas-install-") as tmp:
            venv = Path(tmp) / "venv"
            run(["uv", "venv", str(venv)])
            run([
                "uv", "pip", "install", "--python", str(venv / "bin" / "python"),
                "-r", str(PACKAGE_DIR / "requirements.lock"),
            ])
            run([
                "uv", "pip", "install", "--python", str(venv / "bin" / "python"),
                "--no-deps", str(PACKAGE_DIR),
            ])
            probe = subprocess.run(
                [
                    str(venv / "bin" / "python"),
                    "-c",
                    (
                        "import review_schemas as r\n"
                        "from importlib.metadata import version\n"
                        "assert version('review-schemas') == '0.3.0'\n"
                        f"assert list(r.__all__) == {EXPECTED_EXPORTS!r}\n"
                        "import pathlib\n"
                        "assert 'site-packages' in pathlib.Path(r.__file__).parts\n"
                    ),
                ],
                cwd=tmp,
                capture_output=True,
                text=True,
                check=False,
            )
        assert probe.returncode == 0, probe.stderr


def run(cmd: list[str]) -> None:
    """Run a declared install step, failing the test with its output on error."""
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"{' '.join(cmd)}\n{proc.stderr}"
