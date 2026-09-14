"""Report storage: read the finalized review, write rendered report artifacts.

Shares the artifact server's bucket (increment-3 decision) but never its
`runs/<run>/artifacts/` prefix, so the artifact server's JSON listing is
unaffected:

    runs/<run>/artifacts/<id>.json     artifact-server layout (READ only)
    runs/<run>/reports/<id>.<ext>      rendered MD/PDF bytes
    runs/<run>/reports/<id>.json       the report ArtifactReference
    runs/<run>/report-idem/<format>    (run, format) -> report + final review

Idempotency follows the artifact server's claim-before-write pattern: the
`(run, format)` key is claimed with a generation-0 precondition before any
object is written; a crash between claim and write leaves an orphaned key
whose retry rewrites the record (rendering is deterministic, so the bytes
are reconstructible). The key payload pins the finalized-review artifact id
and checksum — a retry against the *same* reference returns the existing
report (`created = false`); a different reference for the same identity is
an `IdempotencyConflict` (maps to `IDEMPOTENCY_KEY_REUSED`).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from google.cloud.exceptions import PreconditionFailed

from review_schemas.facilitator import FinalizedReview
from review_schemas.mcp import RenderReportInput, RenderReportOutput
from review_schemas.synthesis import ArtifactReference

from report_mcp.render import render


class FinalizedReviewNotFound(Exception):
    """No finalized-review record for this artifact id within the run."""


class IdempotencyConflict(Exception):
    """The (run, format) identity was reused with a different final review."""


_FINAL_KEY = "runs/{run}/artifacts/{artifact_id}.json"
_REPORT_KEY = "runs/{run}/reports/{artifact_id}.{ext}"
_META_KEY = "runs/{run}/reports/{artifact_id}.json"
_IDEM_KEY = "runs/{run}/report-idem/{format}"

#: Wire form (schemas.md ArtifactReference literals).
_CONTENT_TYPE = {"md": "text/markdown", "pdf": "application/pdf"}
#: GCS upload form — MD carries the UTF-8 charset so browsers never guess
#: cp1252 and render the em dash as mojibake (found live on story-07).
_UPLOAD_CONTENT_TYPE = {
    "md": "text/markdown; charset=utf-8",
    "pdf": "application/pdf",
}


class ReportStore:
    """Reads finalized reviews and persists rendered reports.

    `endpoint` targets fake-gcs-server locally; it is None against real GCS
    in Cloud Run — the same code path either way.
    """

    def __init__(self, *, bucket: str, endpoint: str | None = None, project: str | None = None) -> None:
        self._bucket_name = bucket
        self._endpoint = endpoint
        self._project = project
        self._client: storage.Client | None = None

    def _bucket(self):
        if self._client is None:
            options = {"api_endpoint": self._endpoint} if self._endpoint else None
            # An explicit endpoint means the local fake-GCS profile: no ADC
            # in that container, and the target accepts anonymous access.
            credentials = AnonymousCredentials() if self._endpoint else None
            self._client = storage.Client(
                project=self._project,
                client_options=options,
                credentials=credentials,
            )
        return self._client.bucket(self._bucket_name)

    def render_report(self, request: RenderReportInput) -> RenderReportOutput:
        """Render one report; idempotent per (story_run_id, format)."""
        record = self._read_finalized_review(request)
        content = FinalizedReview.model_validate(record["content"], strict=False)
        rendered = render(content, request.format)
        artifact_id = f"art-{uuid.uuid4()}"
        winner = self._claim(request, artifact_id, record)
        if winner is not None:
            existing = self._read_meta_or_none(request.story_run_id, winner["artifact_id"])
            if existing is not None:
                return RenderReportOutput(
                    reference=ArtifactReference.model_validate(existing, strict=False),
                    format=request.format,
                    created=False,
                )
            # Orphaned key from a crash window: write the report it points at.
            artifact_id = winner["artifact_id"]
        reference = self._new_reference(request, artifact_id, rendered)
        self._write_report(request, reference, rendered)
        return RenderReportOutput(reference=reference, format=request.format, created=True)

    # -- finalized review -------------------------------------------------

    def _read_finalized_review(self, request: RenderReportInput) -> dict:
        """The finalized-review record, run-scoped and type-checked."""
        key = _FINAL_KEY.format(
            run=request.story_run_id,
            artifact_id=request.final_review_reference.artifact_id,
        )
        blob = self._bucket().blob(key)
        if not blob.exists():
            raise FinalizedReviewNotFound(
                "finalized-review artifact "
                f"{request.final_review_reference.artifact_id!r} not found in run "
                f"{request.story_run_id!r}"
            )
        record = json.loads(blob.download_as_bytes())
        if record.get("reference", {}).get("type") != "finalized-review":
            raise FinalizedReviewNotFound(
                f"artifact {request.final_review_reference.artifact_id!r} in run "
                f"{request.story_run_id!r} is not a finalized review"
            )
        if (
            record["reference"]["checksum_sha256"]
            != request.final_review_reference.checksum_sha256
        ):
            raise ValueError(
                "finalized-review reference checksum does not match the stored record"
            )
        return record

    # -- idempotency -------------------------------------------------------

    def _claim(self, request: RenderReportInput, artifact_id: str, record: dict) -> dict | None:
        """Claim the (run, format) identity; None when this call won it."""
        final_reference = record["reference"]
        payload = json.dumps(
            {
                "artifact_id": artifact_id,
                "final_review_artifact_id": request.final_review_reference.artifact_id,
                "final_review_checksum": final_reference["checksum_sha256"],
            }
        )
        key_blob = self._bucket().blob(_IDEM_KEY.format(run=request.story_run_id, format=request.format))
        try:
            key_blob.upload_from_string(payload, if_generation_match=0)
            return None
        except PreconditionFailed:
            winner = json.loads(key_blob.download_as_bytes())
            same_reference = (
                winner.get("final_review_artifact_id")
                == request.final_review_reference.artifact_id
                and winner.get("final_review_checksum")
                == final_reference["checksum_sha256"]
            )
            if not same_reference:
                raise IdempotencyConflict(
                    f"report {request.format!r} already rendered for run "
                    f"{request.story_run_id!r} from a different finalized review"
                ) from None
            return winner

    # -- writing -----------------------------------------------------------

    def _new_reference(
        self, request: RenderReportInput, artifact_id: str, rendered: bytes
    ) -> ArtifactReference:
        version = self._next_version(request.story_run_id, f"report-{request.format}")
        return ArtifactReference(
            artifact_id=artifact_id,
            story_run_id=request.story_run_id,
            type=f"report-{request.format}",
            perspective=None,
            version=version,
            created_at=datetime.now(UTC),
            content_type=_CONTENT_TYPE[request.format],
            checksum_sha256=hashlib.sha256(rendered).hexdigest(),
        )

    def _next_version(self, run: str, report_type: str) -> int:
        """Versioning assumes one report per (run, format) (the idempotency
        key enforces it); the scan exists so a future re-render shape stays
        monotonic, scoped to the report type like the artifact server's
        (type, perspective) rule."""
        versions = [
            reference.version
            for reference in self._report_references(run)
            if reference.type == report_type
        ]
        return max(versions, default=0) + 1

    def _report_references(self, run: str) -> list[ArtifactReference]:
        return [
            ArtifactReference.model_validate(json.loads(blob.download_as_bytes()), strict=False)
            for blob in self._bucket().list_blobs(prefix=f"runs/{run}/reports/")
            if blob.name.endswith(".json")
        ]

    def _write_report(
        self, request: RenderReportInput, reference: ArtifactReference, rendered: bytes
    ) -> None:
        bucket = self._bucket()
        content = bucket.blob(
            _REPORT_KEY.format(
                run=request.story_run_id,
                artifact_id=reference.artifact_id,
                ext=request.format,
            )
        )
        try:
            content.upload_from_string(
                rendered,
                content_type=_UPLOAD_CONTENT_TYPE[request.format],
                if_generation_match=0,
            )
        except PreconditionFailed:
            # Crash window between the two writes: the orphan-retry path
            # can find its content object already written. Rendering is
            # deterministic, so identical bytes are expected — anything
            # else is a real conflict and re-raises.
            existing = content.download_as_bytes()
            if hashlib.sha256(existing).hexdigest() != reference.checksum_sha256:
                raise
        meta = bucket.blob(
            _META_KEY.format(run=request.story_run_id, artifact_id=reference.artifact_id)
        )
        try:
            meta.upload_from_string(
                json.dumps(reference.model_dump(mode="json")), if_generation_match=0
            )
        except PreconditionFailed:
            if not meta.exists():
                raise

    def _read_meta_or_none(self, run: str, artifact_id: str) -> dict | None:
        blob = self._bucket().blob(_META_KEY.format(run=run, artifact_id=artifact_id))
        if not blob.exists():
            return None
        return json.loads(blob.download_as_bytes())
