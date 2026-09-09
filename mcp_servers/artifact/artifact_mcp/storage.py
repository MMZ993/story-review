"""GCS-backed artifact store (the design's `GcsArtifactService`).

Implements the artifact-server rules from docs/design/mcp-servers.md:

- **Lineage scoping**: every object lives under `runs/<story_run_id>/`, so
  a read cannot cross runs even by artifact id (an id from another run is
  `ARTIFACT_NOT_FOUND`, not a leak).
- **Idempotency**: an index object per `(story_run_id, type, idempotency_key)`
  written with a generation-0 precondition points at the one artifact that
  key produced; a retry with identical canonical content returns that
  reference (`created = false`), different content raises
  `IdempotencyKeyReused`.
- **Immutability**: artifact objects are written once (generation-0
  precondition) and never rewritten; a re-review saves a new artifact with
  `version = max(existing) + 1` for its `(type, perspective)` pair.
- **Ordering**: `list_artifacts` sorts by `(type, perspective, version)`
  with limit/offset paging and flags `is_latest` per type/perspective.

Object layout inside the bucket (internal; tools expose only
`ArtifactReference`, never these URIs):

    runs/<run_id>/artifacts/<artifact_id>.json   record + canonical content
    runs/<run_id>/idem/<type>/<idempotency_key>  key -> artifact id

Errors raised: `ArtifactNotFound`, `IdempotencyKeyReused`, and
`google.cloud.exceptions.GoogleCloudError` subclasses on storage failures
(mapped by `errors.py` at the tool boundary). Constructor performs no I/O;
the client is created lazily so tests can build the service cheaply.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from google.cloud.exceptions import PreconditionFailed

from review_schemas.mcp import (
    GetArtifactInput,
    GetArtifactOutput,
    ListArtifactsInput,
    ListArtifactsOutput,
    SaveArtifactInput,
    SaveArtifactOutput,
)
from review_schemas.synthesis import ArtifactReference


class ArtifactNotFound(Exception):
    """The artifact id does not exist within the requested story run."""


class IdempotencyKeyReused(Exception):
    """The idempotency key was reused with different canonical content."""


_RECORD_PREFIX = "runs/{run}/artifacts/"
_RECORD_KEY = "runs/{run}/artifacts/{artifact_id}.json"
_IDEM_KEY = "runs/{run}/idem/{type}/{key}"

#: `content_type` per artifact type (schemas.md ArtifactReference).
_CONTENT_TYPE = {
    "story": "application/json",
    "review-business": "application/json",
    "review-engineering": "application/json",
    "synthesis": "application/json",
    "finalized-review": "application/json",
}


def canonical_checksum(content) -> str:
    """Stable sha256 over the content model's canonical JSON form."""
    payload = json.dumps(
        content.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _sort_key(reference: ArtifactReference) -> tuple[str, str, int]:
    return (reference.type, reference.perspective or "", reference.version)


def _new_artifact_id() -> str:
    return f"art-{uuid.uuid4()}"


class GcsArtifactService:
    """Persistent artifact store over the storage library.

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

    def save(self, request: SaveArtifactInput) -> SaveArtifactOutput:
        """Persist one artifact; idempotent per (run, type, idempotency_key).

        Order matters for crash safety: the idempotency key is claimed
        *before* the record is written, so a crash between the two leaves a
        key pointing at a missing record — the retry path then writes that
        record instead of creating a duplicate version.
        """
        checksum = canonical_checksum(request.content)
        artifact_id = _new_artifact_id()
        winner_id = self._claim_idempotency_key(request, artifact_id)
        if winner_id is not None:
            # Lost the claim (or retried an earlier save): return the
            # winner's reference when the content matches, never a duplicate.
            existing = self._read_or_none(request.story_run_id, winner_id)
            if existing is not None:
                if existing["reference"]["checksum_sha256"] == checksum:
                    return SaveArtifactOutput(
                        reference=ArtifactReference.model_validate(
                            existing["reference"], strict=False
                        ),
                        created=False,
                    )
                raise IdempotencyKeyReused(
                    "idempotency key already used with different content"
                )
            # Orphaned key from a crash window: write the record it points at.
            artifact_id = winner_id
        reference = self._new_reference(request, artifact_id, checksum)
        self._write_record(request, reference)
        return SaveArtifactOutput(reference=reference, created=True)

    def get(self, request: GetArtifactInput) -> GetArtifactOutput:
        """Read one artifact's reference and content, run-scoped."""
        record = self._read_record(request.story_run_id, request.artifact_id)
        return GetArtifactOutput.model_validate(record, strict=False)

    def list(self, request: ListArtifactsInput) -> ListArtifactsOutput:
        """One ordered page of references for the run, `is_latest` flagged."""
        references = self._run_references(request.story_run_id)
        filtered = [
            r
            for r in references
            if request.type in {None, r.type}
            and request.perspective in {None, r.perspective}
        ]
        filtered.sort(key=_sort_key)
        latest = _latest_versions(filtered)
        page = [r for r in filtered][request.offset : request.offset + request.limit]
        return ListArtifactsOutput(
            items=[
                r.model_copy(update={"is_latest": r.version == latest[(r.type, r.perspective)]})
                for r in page
            ],
            total=len(filtered),
        )

    # -- internals --------------------------------------------------------

    def _new_reference(
        self, request: SaveArtifactInput, artifact_id: str, checksum: str
    ) -> ArtifactReference:
        """Versioning assumes orchestration serializes saves per run (the
        design's single-writer shape); two racing writers could pick the
        same version number for the same (type, perspective)."""
        version = self._next_version(request.story_run_id, request.type, request.perspective)
        return ArtifactReference(
            artifact_id=artifact_id,
            story_run_id=request.story_run_id,
            type=request.type,
            perspective=request.perspective,
            version=version,
            created_at=datetime.now(UTC),
            content_type=_CONTENT_TYPE[request.type],
            checksum_sha256=checksum,
        )

    def _next_version(self, run: str, artifact_type: str, perspective) -> int:
        versions = [
            r.version
            for r in self._run_references(run)
            if r.type == artifact_type and r.perspective == perspective
        ]
        return max(versions, default=0) + 1

    def _run_references(self, run: str) -> list[ArtifactReference]:
        """References for the run. O(run size × content size): every record
        download carries its content — acceptable at capstone scale."""
        prefix = _RECORD_PREFIX.format(run=run)
        references = []
        for blob in self._bucket().list_blobs(prefix=prefix):
            record = json.loads(blob.download_as_bytes())
            references.append(
                ArtifactReference.model_validate(record["reference"], strict=False)
            )
        return references

    def _read_record(self, run: str, artifact_id: str) -> dict:
        blob = self._bucket().blob(_RECORD_KEY.format(run=run, artifact_id=artifact_id))
        if not blob.exists():
            raise ArtifactNotFound(f"artifact {artifact_id!r} not found in run {run!r}")
        return json.loads(blob.download_as_bytes())

    def _read_or_none(self, run: str, artifact_id: str) -> dict | None:
        try:
            return self._read_record(run, artifact_id)
        except ArtifactNotFound:
            return None

    def _write_record(self, request: SaveArtifactInput, reference: ArtifactReference) -> None:
        payload = json.dumps(
            {
                "reference": reference.model_dump(mode="json"),
                "content": request.content.model_dump(mode="json"),
            }
        )
        blob = self._bucket().blob(
            _RECORD_KEY.format(run=request.story_run_id, artifact_id=reference.artifact_id)
        )
        blob.upload_from_string(payload, if_generation_match=0)

    def _claim_idempotency_key(self, request: SaveArtifactInput, artifact_id: str) -> str | None:
        """Point the key at its artifact (generation-0 precondition).

        Returns None when this call won the claim; otherwise the artifact id
        the key already points at (the winner of a race or the earlier save
        of a retry).
        """
        key_blob = self._bucket().blob(
            _IDEM_KEY.format(
                run=request.story_run_id, type=request.type, key=request.idempotency_key
            )
        )
        payload = json.dumps({"artifact_id": artifact_id})
        try:
            key_blob.upload_from_string(payload, if_generation_match=0)
            return None
        except PreconditionFailed:
            return json.loads(key_blob.download_as_bytes())["artifact_id"]


def _latest_versions(references: list[ArtifactReference]) -> dict[tuple[str, str | None], int]:
    """Max version per (type, perspective) — the caller's 'latest' rule."""
    latest: dict[tuple[str, str | None], int] = {}
    for reference in references:
        key = (reference.type, reference.perspective)
        latest[key] = max(latest.get(key, 0), reference.version)
    return latest
