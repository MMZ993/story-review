# Runbook 10 — MCP servers (Phase 4)

Codifies the Phase 4 work: three MCP servers (story, artifact, report),
local compose stack, and Cloud Run deploys, per
`docs-local/plans/phase-4-mcp-servers.md` and `docs/design/mcp-servers.md`.
Local increments are no-cost; the deploy increment (Cloud Run + GCS smoke)
is owner-approved before execution.

Status: IN PROGRESS (opened 2026-09-09).

## Increment 0 — shared-schema catch-up + decisions (local, no cost)

Executed 2026-09-09 (session 17). No environment commands — code + tests only:

```
make review-schemas-test   # red first (ImportError: ContextStory), then green
make dataset-test          # untouched loader suite, still green
```

Owner decisions (recorded as D9 amendment 4 in local-decisions.md):
`StoryComment.author` kept; preparation at server startup (HTML flattening +
field mapping in memory, golden-snapshot pinned); PDF library deferred to
increment 3.

Changes (test-first):

- `shared/review_schemas/review_schemas/review.py`: `StoryComment`
  (`author`, `text`, `created_at`) and `ContextStory` (`relation`
  `related|depends`, own `acceptance_criteria` cap 100 + `comments` cap 50)
  added; `StoryDetail` gains `comments` (cap 50, default empty) and
  `context_stories` (cap 5, default empty) — exactly
  `docs/design/schemas.md`.
- `review_schemas/__init__.py`: both models re-exported; exports test list
  updated.
- `pyproject.toml`: version 0.1.0 → 0.2.0 (package-install test updated to
  match).

Evidence: `make review-schemas-test` **151 passed** (147 + 4 new behavior
tests plus extended default assertions in the existing summary/detail test:
valid nested payload, strict-field rejection, relation literal, cap 50/5
overflow); `make dataset-test` **36 passed**.

### Increment 1 correction — runtime story contract (local, no cost)

Owner-approved 2026-09-09. Before story-server preparation began, the owner
identified `StorySummary.quality_class` as an evaluation-data leak: real Azure
DevOps stories do not know their expected review result. The authoritative
schema, shared implementation, and all public API/MCP consumers now omit it;
`dataset` retains its `scenario` only for test evaluation. The new behavior
contract rejects a public story payload carrying `quality_class`.

```
make review-schemas-test  # focused test red first, then 152 passed green
```

### Increment 1 (part 1) — dual-source design + schema + preparation (local, no cost)

Owner decisions (session 19, D10 in local-decisions.md): story MCP gets a
**dual data source** — production path reads live Azure DevOps (PAT: reuse
`rest-verify` from `ado.env`; Secret Manager at increment 5), mock path
serves the frozen dataset from GCS (`make dataset-push`, bucket bootstrap at
increment 5; local tests use a directory location). Source selection =
deployment env `STORY_SOURCE` + orchestration-only per-call override
(option a; stateless server). `StoryId` widened to
`^(story-[0-9]{2}|ado-[0-9]{1,8})$`. Evaluation runs always use `mock`.
Design docs changed atomically and cherry-picked to `docs/initial-frozen`
(`37309db`→`5ab7380`, `336ea8e`→`7eb9cec`).

- `shared/review_schemas` **0.4.0**: `StorySource` + `source` field on
  `ListStoriesInput`/`GetStoryInput` + widened `StoryId` (test-first red:
  missing `source` attr / `ado-5` rejected).
- `mcp_servers/story/` uv package `story-mcp`: `flatten.py` (stdlib HTML
  flattener), `prepare.py` (ADO→`StoryDetail` per the owner-approved mapping
  table — presented and approved in chat; scenario/template never mapped),
  45 **golden snapshots** in `tests/golden/` (owner-reviewed once,
  `tests/generate_golden.py` regenerates).
- New Makefile target `mcp-story-test` (pattern of `dataset-test`, with
  `--with ../../dataset/loader` for the envelope models).

```
make mcp-story-test        # red first (ModuleNotFoundError story_mcp[.prepare]), then 21 passed
make review-schemas-test   # 154 passed (152 + 2 new source/id tests)
make dataset-test          # 36 passed (untouched)
```

Gotchas learned:

- Identifier check with an unset variable matches everything (empty regex
  alternation) — always source BOTH `home.env` and `ado.env` before `rg
  -l "$PROJECT_ID|$ADO_ORG|..."`; post-commit re-check was clean.
- Context envelopes (`dataset/stories/context/`) are full envelopes with a
  `work_item` key, not bare work items — `ContextIndex.from_items` accepts
  both shapes.
- `StoryComment.created_at` (AwareDatetime, strict) needs a parsed
  `datetime` — `fromisoformat` with `Z`→`+00:00`, not a raw string.
- Schema-change review deferred to the full increment-1 review (server +
  contract tests still to come).
- (Carried from increment 0) `tests/test_package_install.py` pins both the
  package version and the exact `__all__` list — a version bump or new
  export must update that test in the same change.
- (Carried from increment 0, now superseded by D10) `StoryId` pattern was
  `story-NN` two digits only; now `story-[0-9]{2}|ado-[0-9]{1,8}`.

### Increment 1 (part 1b) — ADO wire models extracted to `shared/ado_wire` (local, no cost)

D9 amendment 6. Split extraction (implementation subagent, owner-reviewed
diff): `WorkItem`/`WorkItemComment` moved verbatim from
`dataset_loader.envelope` to new shared package `shared/ado_wire` (pydantic
only); `StoryEnvelope` + dataset aliases stay in the loader, which
re-exports the moved models. Existing test files byte-identical; new tests
in `shared/ado_wire/tests/` (7). Motivation: the story server (and future
live `azure` source) imports wire shapes without a loader dependency for
them; Docker context shrinks accordingly (still needs `dataset/loader` for
`StoryEnvelope` on the mock path).

```
make ado-wire-test       # 7 passed (red first: ModuleNotFoundError ado_wire)
make dataset-test        # 36 passed (untouched)
make mcp-story-test      # 21 passed
make review-schemas-test # 154 passed (untouched)
```

Gotchas learned:

- A stale uv-cached `dataset-loader` wheel served an old `envelope.py`
  during the refactor — `uv cache clean` resolves it (hit once during
  implementation, verified after).
- Subagent-assessed first (cheap-model read-only pass) that the move could
  keep all three existing test dirs byte-identical — held true; only
  packaging/imports changed.

### Increment 1 (part 2) — story MCP server (local, no cost)

D10 dual-source server implemented (test-first, red at each module):

- `story_mcp/backlog.py` — source-independent core: id-space separation
  (`story-NN` vs `ado-N`, cross-source → `StoryNotFound`), status filter
  (case-insensitive substring), `resolve_source` (None = deployment
  default).
- `story_mcp/mock_source.py` — mock source from a directory or `gs://`
  location (GCS client injectable; tests use a fake). Zero-envelope
  locations and non-directory/gs locations fail loud at construction.
- `story_mcp/azure_source.py` — live ADO REST (PAT basic auth, WIQL +
  workitemsbatch + `$expand=all` + comments API), mapped through the same
  preparation core (`prepare_work_item`, extracted from `prepare_story`
  behavior-identically — goldens stayed green). Transport failures →
  `SourceUnavailable` → `UPSTREAM_UNAVAILABLE` (retryable); missing work
  item → `STORY_NOT_FOUND`. No network in tests (`httpx.MockTransport`
  recorded-shape fixtures).
- `story_mcp/server.py` — MCPServer (mcp 2.1.1) tools `list_stories` /
  `get_story`; flat schemas exactly matching the shared input models;
  unknown-field rejection by inspecting the raw call arguments
  (`context.request_context.params` is a Mapping — `.arguments` is a KEY,
  not an attribute; see gotchas); every failure returns structured
  `ToolError(ErrorBody)` with `is_error` set; correlation id from
  `X-Correlation-Id` (UUID-v4 when supplied, else generated).
- `story_mcp/auth.py` — spike-pattern ID-token middleware (bearer vs
  audience; `/healthz` public; missing audience + auth on → fail-closed
  503); `STORY_AUTH_DISABLED=1` is the local-profile off switch.
  Allowlist `STORY_ALLOWED_CALLERS` (both tools: orchestration +
  facilitator); UNAUTHENTICATED / FORBIDDEN as ToolError payloads.
- `story_mcp/app.py` + `main.py` — env-driven ASGI wiring, stateless
  Streamable HTTP; azure source appears only when its env is complete.
- `mcp_servers/story/Dockerfile` — root context; copies `story_mcp`,
  `review_schemas`, `ado_wire`, and `dataset_loader` (code-only) +
  build-time guard that `dataset/stories`/`dataset/expected` content is
  absent. **NOTE: this needs a repository-layout.md amendment** — the
  current text says "no Dockerfile copies any part of `dataset/`"; the
  mock source reuses the loader's envelope parser (D9 verbatim export
  principle). Owner decision pending.
- `dataset/tools/push_dataset.py` + `make dataset-push` — 48 objects
  (45 stories + 3 context) to `gs://$PROJECT_ID-story-dataset/stories/`;
  expected files never upload; `--dry-run` verified locally. Bucket
  bootstrap stays at increment 5.

```
make mcp-story-test       # 65 passed (red-first per module)
make ado-wire-test        # 7 passed
make dataset-test         # 36 passed
make review-schemas-test  # 154 passed
docker build -f mcp_servers/story/Dockerfile .   # ok; guard RUN passed
# container smoke: /healthz ok, tools/list over Streamable HTTP ok,
# bad STORY_DATASET_LOCATION aborts startup loudly (correct fail-fast)
```

Gotchas learned:

- mcp 2.1.1: FastMCP is renamed `MCPServer`; client yields a 2-tuple;
  client result attr is `is_error`, tool attr `input_schema`; the
  framework strips unknown args before the handler — raw-argument
  rejection must read `context.request_context.params["arguments"]`.
- pytest-asyncio + mcp client streams = cancel-scope teardown noise;
  contract tests use sync tests + `asyncio.run` per scenario (spike's
  sync pattern) — clean.
- `streamable_http_client` against a stateless server needs
  `terminate_on_close=False` (the closing DELETE otherwise hangs/errs).
- MCP client over ASGI needs `asgi-lifespan` (the session manager's task
  group only starts via the app lifespan).
- The Host-header transport-security check needs `http_host` matching
  the client's base_url in tests (spike hit the same).
- `ErrorBody.correlation_id` wants a UUID instance, not a string
  (pydantic `is_instance` validator).
- Story-mcp version bumped 0.1.0 → 0.2.0 (server added).

**Independent read-only review** (subagent): first pass **Needs fixes** —
2 Important, 8 Minor. Fixed same session:

- Important: allowlist fail-open on misconfiguration — with auth enabled
  but `STORY_ALLOWED_CALLERS` unset, any verified principal was served.
  Now `_resolve_callers` derives the bypass solely from auth-disabled (+
  no explicit allowlist); auth enabled + empty env = empty set → all calls
  FORBIDDEN (regression test added).
- Important: azure 404 vs transient conflated — any `SourceUnavailable`
  became STORY_NOT_FOUND. `SourceUnavailable` now carries the HTTP status;
  only 404 maps to STORY_NOT_FOUND (503 regression test added).
- Minor fixed: dead duplicated block in test_azure_source `_route`;
  GCS directory-marker blob guard in `_materialize_bucket`; test renamed
  (`test_story_without_relations_has_no_context_stories`); unexpected
  tool exceptions now log at warning.
- Minor accepted as-is: `internal_error` uses UPSTREAM_UNAVAILABLE (no
  INTERNAL code in the taxonomy); parentless live azure stories raise
  UPSTREAM_UNAVAILABLE — the backlog invariant (stories always under
  Feature→Epic) is guaranteed by the authoring conventions (Runbook 08);
  azure `list_stories` caps at the schema's 50 summaries (demo backlog
  is 42–45); malformed X-Correlation-Id replaced, not rejected.
- Repository-layout.md amended for the code-only `dataset/loader` image
  copy: main `ad841b3`, frozen cherry-pick `2a29f71` (owner decision (a)).

## Increment 2 — artifact MCP server (local, fake GCS; no cost)

**Status: DONE** (session 21, 2026-09-10).

What was built (test-first, package `mcp_servers/artifact/`, uv package
`artifact-mcp` 0.1.0):

- `storage.py` — `GcsArtifactService` over `google-cloud-storage` with an
  injectable endpoint (fake-gcs-server locally, real GCS in Cloud Run —
  same code path). Object layout `runs/<run>/artifacts/<art-id>.json`
  (record + canonical content) and `runs/<run>/idem/<type>/<key>` (key →
  artifact id). Immutability via generation-0 preconditions on both writes.
  **Claim-before-write order** for crash safety: the idempotency key is
  claimed first, so a crash between claim and record leaves an orphaned
  key whose retry writes the missing record (test covers it) instead of a
  duplicate version. Version = max+1 per (type, perspective) — assumes
  orchestration serializes saves per run (documented in code). `list`
  sorts by (type, perspective, version), paginates, flags `is_latest`.
- `server.py` — `MCPServer("artifact")` with `save_artifact` /
  `get_artifact` / `list_artifacts` over the shared input models;
  per-tool allowlists (`save` = orchestration only, reads = orchestration
  ∪ facilitator; `CallerRoles`); unknown-field rejection via raw call
  arguments (Runbook-10 gotcha); input validation with
  `model_validate(..., strict=False)` — wire JSON carries UUIDs as
  strings and the strict models reject those instances otherwise.
- `errors.py` — ToolError mapping incl. `ARTIFACT_NOT_FOUND`,
  `IDEMPOTENCY_KEY_REUSED` (both non-retryable), `PreconditionFailed` →
  retryable UPSTREAM_UNAVAILABLE, last-resort internal errors
  **non-retryable**.
- `auth.py` — spike-pattern ID-token middleware (env renamed
  `ARTIFACT_*`); `app.py`/`main.py` env-driven stateless wiring —
  `ARTIFACT_BUCKET` (validated non-empty at build; empty would otherwise
  fail opaquely at the first tool call), `ARTIFACT_GCS_ENDPOINT`,
  `ARTIFACT_SERVICE_URL`, `ARTIFACT_AUTH_DISABLED`,
  `ARTIFACT_{ORCHESTRATION,FACILITATOR}_CALLERS` (both fail-closed as
  empty sets when unset, same semantics as the story fix).
- Dockerfile (root context; ships `artifact_mcp` + `review_schemas`
  code-only + the dataset-absence guard). Container smoke over real HTTP:
  healthz OK against a fake-gcs endpoint.
- Makefile `mcp-artifact-test`: starts `fsouza/fake-gcs-server:latest`
  (port 9023, readiness-checked with explicit failure), runs pytest with
  `ARTIFACT_TEST_GCS_ENDPOINT`, tears the container down on exit.

Evidence (local, session 21): `make mcp-artifact-test` **32 passed**
(14 storage + 13 server/contract + 5 ingress); other suites re-run green
(review-schemas 154, dataset 36, story 67, ado-wire 7); Docker build +
container healthz smoke OK; `git diff --check` clean.

Gotchas learned:

- `RunId`/`ArtifactId` are dashed-uuid ids (`run-{uuid}` / `art-{uuid}`,
  40 chars) — `.hex` forms are one char short of the pattern minimums.
- Strict shared models reject their own JSON round trip (`strict=True`
  refuses string datetimes/UUIDs) — revalidate persisted records with
  `model_validate(..., strict=False)`.
- The StreamableHTTP session manager `.run()`s once per app instance —
  contract tests must build a **fresh app per round trip** (hit as
  "RuntimeError: can only be called once per instance").
- fake-gcs-server listens on **4443** by default (`-scheme http` only
  switches the scheme, not the port); it *does* enforce
  `ifGenerationMatch=0` (returns PreconditionFailed 412).
- `_new_reference` briefly ignored the claimed artifact id (regenerated
  its own) — retries created "duplicate" records under new ids; caught by
  the retry test, fixed by threading the id through.

**Independent read-only review** (subagent): first pass **Needs fixes** —
3 Important, 6 Minor. Fixed same session:

- Important: lost idempotency race with identical content raised
  IDEMPOTENCY_KEY_REUSED instead of returning the winner (retry poisoned);
  claim-loss now falls through to checksum comparison.
- Important: crash window between record write and key claim could
  duplicate versions; claim order reversed (see above) + orphan-key test.
- Important: `internal_error` was retryable (default flipped during the
  port) — against "retry hints only where safe"; now non-retryable
  (regression test).
- Minor fixed: `STORY_AUTH_DISABLED` copy-paste in the auth docstring;
  string-matched PreconditionFailed branch → `isinstance` with
  `google.cloud.exceptions`; five ingress middleware tests ported (401
  missing/invalid token, 503 missing audience, healthz public, verified
  allowlisted caller succeeds); fake-gcs readiness loop now fails
  explicitly; empty `ARTIFACT_BUCKET` rejected at app build.
- Minor documented in code, not changed: `_run_references` downloads full
  records per list/save (O(run × content) — capstone-scale acceptable);
  version assignment assumes orchestration is the serialized writer per
  run; auth middleware remains a story-server copy (extraction candidate
  if the report server needs a third copy — increment 3 decision).

## Increment 3 — report MCP server + mcp_ingress extraction (local, fake GCS; no cost)

Executed 2026-09-10 (session 22). No environment commands — code + tests +
local Docker builds/smokes only:

```
make mcp-report-test    # 34 passed (7 render + 9 storage + 18 server/ingress)
make mcp-ingress-test   # 7 passed
make mcp-story-test     # 67 passed   make mcp-artifact-test  # 32 passed
make review-schemas-test  # 154       make dataset-test       # 36
make ado-wire-test        # 7
docker build -f mcp_servers/report/Dockerfile .    # OK (also story + artifact rebuilt)
# container smoke: /healthz 200; missing REPORT_BUCKET aborts loudly;
# real render_report round trip over HTTP vs fake GCS (pdf created=True,
# retry created=False); anonymous-credentials fix required (see gotchas)
```

Owner decisions (settled in chat before code, per the increment-3 plan):

- **PDF library: fpdf2** (pure Python, ~2 MB image delta, deterministic
  bytes; weasyprint rejected — pango/cairo bloat + determinism risk).
  Markdown side rendered directly from the block structure (no
  markdown-it-py dependency needed).
- **Auth middleware extracted now**: `shared/mcp_ingress/` (package
  `mcp-ingress` 0.1.0) — the story/artifact copies were diff-verified
  identical modulo logger/contextvar names, deleted, and both servers +
  Dockerfiles + Makefile rewired. New `make mcp-ingress-test` (7 tests).
- **Report storage**: own `ReportStore` module on the SAME bucket as the
  artifact server, disjoint prefixes — reads `runs/<run>/artifacts/<id>.json`
  (artifact layout), writes `runs/<run>/reports/<id>.<ext>` +
  `<id>.json` + idempotency key `runs/<run>/report-idem/<format>`. No
  MCP-over-HTTP hop to the artifact server (report types are outside
  `SaveArtifactType` anyway).

Changes (test-first; red confirmed `ModuleNotFoundError: report_mcp`):

- `mcp_servers/report/` (uv package `report-mcp` 0.1.0):
  - `render.py` — `FinalizedReview` → block list → deterministic MD / PDF
    (fpdf2, pinned `CreationDate` 2000-01-01, no /ID trailer; PDF bytes
    latin-1 via built-in fonts — non-latin text degrades vs MD,
    documented). Byte-identical double renders pinned by test.
  - `storage.py` — claim-before-write idempotency per (run, format);
    key payload pins the finalized-review artifact id + checksum → same
    reference retry returns existing (`created=false`), different
    reference raises `IdempotencyConflict` (→ `IDEMPOTENCY_KEY_REUSED`);
    orphan-key crash window retried by rewriting the record; content/
    meta two-write crash window handled by checksum-verified tolerance of
    the already-written content object; caller-reference checksum checked
    against the stored record (mismatch → `VALIDATION_ERROR`);
    version scan scoped to the report type.
  - `server.py` — `render_report` (orchestration-only allowlist, absent
    principal fails closed), unknown-field rejection via raw call
    arguments, dispatch skeleton identical to the artifact server.
  - `errors.py` — `ARTIFACT_NOT_FOUND` / `IDEMPOTENCY_KEY_REUSED` /
    `RENDER_FAILED` (fpdf2 `FPDFException`) non-retryable;
    `PreconditionFailed` → retryable `UPSTREAM_UNAVAILABLE`; internal
    errors non-retryable.
  - `app.py`/`main.py` — `REPORT_*` env (bucket validated at build), /healthz
    public, `mcp_ingress` middleware in the production shape.
  - Dockerfile (root context, `report_mcp` + `review_schemas` +
    `mcp_ingress` code-only, dataset-absence guard).
  - `make mcp-report-test` (fake-gcs-server :9024, readiness-checked).

**Independent read-only review** (subagent): first pass **Needs fixes** —
1 Important, 5 Minor; all fixed same session + follow-up review
**Ready to proceed**:

- Important: `_write_report` two-write crash window made the retry path
  permanently stuck (content-object generation-0 precondition fails on
  every retry) — now tolerated when the existing bytes' sha256 matches
  the reference checksum; regression test seeds idem key + content blob
  without meta.
- Minors fixed: `_next_version` scoped per report type; stored-record
  checksum comparison against the caller's reference; fpdf2 determinism
  comment corrected (falsy `file_id()`, /Producer version, latin-1
  divergence); stored-bytes checksum assertion in the save test.

Gotchas learned (session 22):

- **ADC inside containers**: `storage.Client()` demands ADC even with an
  endpoint override — the report server now uses `AnonymousCredentials`
  when `REPORT_GCS_ENDPOINT` is set (fake-GCS profile only). **The story
  and artifact servers have the same latent gap** (their session-20/21
  container smokes were healthz-only, which is why it never surfaced);
  must be fixed for the compose increment 4 — same one-line change.
- **fake-gcs-server loopback binding**: `-p 127.0.0.1:9025:4443` is NOT
  reachable from other containers via `172.17.0.1`; publish on 0.0.0.0
  (`-p 9025:4443`) for cross-container smokes.
- fpdf2 `file_id` is a *method* (overridable), not a settable attribute —
  assigning a string breaks serialization with a confusing TypeError.
- report `requirements.in` cannot name local packages (`review-schemas`,
  `mcp-ingress`) — uv pip compile fails; they ride along via
  `--with-editable` in tests and COPY in Dockerfiles (artifact-server
  convention).
