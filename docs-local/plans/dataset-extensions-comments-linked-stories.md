# Dataset extensions — comments and linked context stories (planning only)

Status: PLANNING (2026-09-08, session 14, owner-raised). Nothing here is
implemented; both extensions change `docs/` design and the data structure, so
they proceed docs-first in a dedicated session. Mock data authoring for
extension 2 is explicitly deferred — only the data structure is codified now.

Motivation (owner): both are realism gaps. Blocked/contested stories in real
backlogs accumulate discussion in **comments**, and implementation stories
often **link** to their analysis/precursor stories while some context lives
only in the linked item.

## Extension 1 — comments as review input

### Mock data (3 new stories, owner-specified)

| # | Content | Comments | Expected effect |
|---|---------|----------|-----------------|
| C-1 | clean story | benign discussion (questions + answers, resolved) | verdict unchanged vs no-comments clean — comments must not create findings |
| C-2 | ambiguous for BOTH perspectives | comments clarify only ONE side (e.g. business questions answered, engineering questions not) | findings only on the side NOT covered by comments; the clarified side is positive |
| C-3 | description complete for ONE side only (e.g. clear business value, engineering-thin) | comments carry the missing information for the OTHER side | both reviews positive — reviewers must incorporate comment content as story context |

Placement: these are new **content variants**, not new templates — author in
T1 under the existing scenarios' worlds (suggest: C-1 clean world, C-2 a new
ambiguous scenario, C-3 an engineering-weak-world variant), case ids
`<template>/<scenario>-comments` per the D9 `-suffix` rule... note the suffix
rule currently means "duplicate for stress"; confirm the intended id form
(e.g. `t1/clean-comments`) when authoring.

### What must change (evaluation)

1. **Export (`dataset/tools/export_ado.py`)**: comments are NOT part of
   `work-item show` output — they need the ADO comments API
   (`GET _apis/wit/workItems/{id}/comments` via `az rest`, or the REST
   fallback). Per-story fetch + sanitize (author identities anonymized like
   the export; comment timestamps kept or normalized — decide at export
   inspection). Envelope gains `comments: [...]`; bump handling: optional
   field, `schema_version` stays 1 unless shape breaks consumers (prefer
   additive-only).
2. **Data classification (D9 deferred item — now forced)**: comments are
   **semantic review input**, not display decoration — they can carry facts
   that resolve or create findings. Record in the metadata classification.
3. **`docs/` design changes (owner approval required — design change)**:
   - `schemas.md`: `StoryDetail` gains `comments` (list; shape TBD: plain
     `Text` per comment vs structured `{author?, text, created_at}` — start
     structured, flatten in the MCP).
   - `agents.md`: reviewers' input contract includes comments; findings may
     reference comment content (does `references_po_question` need a sibling
     like `references_comment`? evaluate — maybe not for v1).
   - `mcp-servers.md` / `api-contract.md`: `get_story` returns comments;
     `StorySummary`/list probably unchanged.
   - Phase 2 `review_schemas` impact: only if StoryDetail-like models live
     there — check; expected: no change (StoryDetail is Phase 4 MCP output).
4. **Manual plans + expected files** for the 3 cases (new arcs: comment-
   invariance for C-1, one-sided clarification for C-2, comment-completion
   for C-3). Update `docs/quality/mock-data.md` scenario table (like the
   hidden-conflict row, owner-approved).
5. **Test suite**: loader (Runbook 09 increment 4) validates the comments
   field when present; no-comments stories must keep working (backwards
   compatible).

### Open decisions to settle in the extension session

- Are comments ALWAYS passed to reviewers, or does the MCP truncate/summarize
  long threads (limit N comments / M chars — pick the constant)?
- Do PO-script turns ever reference comment content in `extra_context`?
- C-2's "comments answer business questions": who answers in the thread —
  the PO persona? Author display names are anonymized (`Story Author`) —
  comments may need richer anonymized personas (e.g. "PO", "Dev") for
  realistic dialogue; decide the persona scheme at authoring.

## Extension 2 — linked context stories (structure now, data later)

Owner decision: **defer mock data**; codify the data structure so adding
linked-story cases later is pure data preparation.

### Target model

- A test case = **one main story** (reviewed) + 0..X **linked context
  stories** (reference material; never reviewed themselves). X = 5 proposed
  (align with any existing context limits in `docs/` — check
  `api-contract.md`/`schemas.md` before fixing the number).
- Realistic driver: analysis story → implementation story, where the
  implementation story should be self-contained but some context was not
  copied over; the reviewer may need the linked item to spot the gap.

### What must change (evaluation)

1. **Dataset structure (codify NOW)**:
   - Envelope gains optional `linked_stories: [case_id...]` (references, not
     embedded — linked stories are themselves story files in
     `dataset/stories/`, case ids pointing at their files; a story referenced
     as context may or may not also be a test case of its own).
   - ADO authoring: linked via work-item relations (e.g.
     `System.LinkTypes.Related` / `Depends` / custom); the export already
     preserves `relations` — extend resolution to map relation URLs to case
     ids (needs an ADO-id → case map at export time — the provenance map
     already provides it; linked stories not in the provenance map need ids
     there too, or a separate linked-story registry).
   - Context stories that exist ONLY as context (no own test case): decide
     location — `dataset/stories/context/` currently means epic/features;
     either widen it or add `dataset/stories/linked/`. Prefer: linked
     context stories live under their template folder like any story, with
     `is_test_case: false` flag or simply no expected file (loader derives
     the distinction from the referencing case).
2. **`docs/` design changes (owner approval)**:
   - `schemas.md`: `StoryDetail` gains `context_stories` (list of summaries
     or a trimmed detail — reviewers need enough to extract the uncopied
     context, so at least description-level; decide flattened vs structured).
   - `api-contract.md` / `mcp-servers.md`: `get_story` includes linked
     stories within the X limit; `list_stories` marks main stories only.
   - `agents.md`: reviewer input includes context stories, clearly framed as
     "related items — the story under review is the main one" (prompt-
     design concern: avoid reviewers reviewing the linked items).
3. **Orchestration/session runner (Phase 4/9 concern, note only)**: a session
   loads main + linked; expected files assert against the main story's arc.

### Open decisions to settle

- The X limit value (5?) and whether it is enforced by MCP, schema, or both.
- Which ADO link types map to "context story" (Related vs Depends vs
  Hierarchy is already epic/feature — exclude Hierarchy).
- Whether context stories appear in `epic_context`-style flattened text or
  as a separate `StoryDetail` list (prefer separate list).

## Suggested session order (the extension session)

1. Settle open decisions with the owner; apply the `docs/` design changes
   (schemas/agents/api-contract/mcp-servers) — design change, owner-approved.
2. Codify extension 2's dataset structure (envelope field, export relation
   resolution, loader validation) — structure only, no mock data.
3. Extension 1: export comments support + sanitize; author the 3 comment
   stories in ADO (T1); manual plans + expected files; matrix note in
   story-templates.md (comments as a content axis, not a template).
4. Record everything: D9 amendment (comments = semantic input; linked-story
   structure), Runbook 08/09 entries, HANDOFF.

Dependencies: Runbook 09 increments 3–4 (expected files + loader) can land
first — both extensions are additive and must stay backwards compatible with
the 42 existing cases.
