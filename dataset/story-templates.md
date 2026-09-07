# Story description templates — `dataset/story-templates.md`

Canonical per-scenario fact lists live in
[`canonical-facts.md`](canonical-facts.md) — renderers work from there.

## Template vs. story quality — two independent axes

- **Template** = the *format* a team uses (structure, sections, conventions).
- **Story quality** = how well the *content* is filled in (complete, measurable,
  justified vs. vague, partial, missing).

They are independent. A good template can be filled vaguely; a free-text story
can contain everything necessary — just harder to read. Real teams don't always
follow their own template, so the dataset deliberately mixes both axes.

**System requirement this dataset tests (format invariance):** the same story
content, expressed through any template, must yield the same review outcome —
the same findings flagged, same decisions, same readiness. A missing piece of
information must be flagged no matter how beautiful the template that omits it;
conversely, complete information must not be missed because the format is plain.
Formatting itself may produce at most **info-level** reviewer notes, never
routed findings or readiness changes.

Invariance is asserted on **normalized, semantic grounds** (independent review,
2026-09-07): expected files assert semantic finding codes + severity,
readiness, decisions, and required clarification topics — NOT verbatim prose,
wording, ordering, or location references, which may legitimately vary with
format. Titles are rendering targets: every fact expressed in a template's
title (e.g. T4's full story sentence) must also exist in the canonical content
so it is preserved across variants.

## Canonical content model

Every scenario has a canonical, field-level semantic representation — the
facts, criteria, constraints, dependencies, and value statement — defined once
per scenario. Each template variant is **rendered from the canonical model**,
never paraphrased from another variant; equivalence between variants is judged
against the canonical facts, not prose. Rules:

- Renderers (including future subagent renderers) work from a must-retain /
  must-not-add fact list per scenario; automated canonical-fact comparison
  gates each variant before it enters the dataset.
- T6 (free text) renderings must contain **every canonical fact, including
  criteria, in prose** — terse/cryptic phrasing and unstructured placement are
  the format variation; missing facts belong to the quality axis, not T6.
- Metadata fields (dependencies, sign-off, deadline, links...) are part of the
canonical model when they are semantic review inputs; display-only decoration
  is not. (Full classification happens with the expected-file design.)

## Matrix structure

Scenarios (clean / business-weak / engineering-weak / conflicting /
partial-resolution / unresolvable) × templates (T1–T6), with story quality as a
third dimension in stress datasets (well-filled / partially vague / vague —
including deliberately mismatched pairs: beautiful template, vague content, and
vice versa). All scenarios are first authored in T1 (baseline column); other
columns are rendered from the canonical model afterwards — mechanical
rendering work suited to subagents once positioning is settled so columns do
not interfere. How the matrix is structured inside Azure DevOps itself
(separate projects vs. teams/area paths in one project) is an open decision to
be recorded with D9.

**T5 is a work-item TYPE variant, not a pure format variant:** an enabler
story changes the valid interpretation of actor and value ("no end user" is
material in a user-story column but normal for an enabler). T5 stories are
therefore NOT renderings of the user-actor scenarios; they are self-contained
enabler stories per scenario, excluded from cross-template invariance
assertions (a future enabler-column invariance test compares enabler stories
only).

**HTML/rich text is a separate ingestion-stress variable:** ADO description and
AC fields are HTML; invariance tests run against a normalized-text contract,
and a separate stress set exercises HTML lists, headings, links, tables, and
line breaks (Phase 4 translation concern).

Templates are ordered from most ceremonial/structured to least. T1 and T2
share a sectioned skeleton; T2's distinct value is the **field-location test**
(criteria source-of-truth in the description with the AC field empty), not a
wholly different formatting family — kept deliberately.

## T1 — Structured sections + explicit criteria

```text
Title:       short designation ("Invoice PDF in order confirmation email")
Description:
  <Context: what exists today, what is wrong/missing.>
  <Reason: who asked, business impact, links to evidence.>
  <Scope: explicit out-of-scope list.>
Acceptance Criteria (field):
  explicit criteria, one per behavior incl. failure/edge paths —
  either Given/When/Then scenarios or an imperative checklist.
Meta: dependencies, links, sign-off — only when they exist.
```

The most prescriptive format: fixed sections and explicit criteria.

## T2 — Sectioned maintenance style

No acceptance criteria in the field — criteria-like content lives inside the
description, and the description is the source of truth for review.

```text
Title:       short designation
Description:
  Description: what the item is
  Reason: what is happening, who requested, what breaks
  Implementation: how, links, API/FIX details as needed
  For this story: concrete verification steps (the de-facto criteria)
  ---
  Demo: yes/no
  Dependencies: ...
  Deadline: ...
  Requested by: ...
  Contacts: ...
  Sign-off: ...
Acceptance Criteria (field): (empty)
```

Still structured and equally reviewable — but differently: the reviewer must
locate the criteria inside free-form text.

Note (deferred design input for the agents phase): reviewers should be designed
to use the description for assessment when the AC field is empty.

## T3 — Job Story

```text
Title:       short designation
Description:
  free paragraphs — background, why now, constraints; no fixed sections
Acceptance Criteria (field):
  - bullet list, one per behavior (can be informal sentences)
Meta: optional
Story framing (title or first line):
  "When <situation>, I want <motivation>, so I can <expected outcome>."
```

Intent-first framing (context → motivation → outcome) instead of the
role-focused user story. Tests that reviewers handle situation-driven intent.

## T4 — Classic user story (ceremony standard)

```text
Title:       "As a <role>, I want <capability> so that <benefit>"
Description:
  free paragraphs — background, why now, constraints; no fixed sections
Acceptance Criteria (field):
  - bullet list, informal (sentences, not necessarily measurable)
Meta: rarely used
```

The textbook Agile format — familiar and widely used as the de-facto standard.
Loose description and informal criteria make completeness harder to judge than
T1–T2.

## T5 — Enabler / technical story (TYPE variant — not in the invariance grid)

```text
Title:       short designation
Story framing (title or first line):
  "As the engineering team, we need <capability> so that <outcome>" —
  or a system actor ("As the order service, ..."). Non-user-facing value.
Description:
  <what exists today, what is wrong/missing, why now.>
  <links: runbooks, incidents, metrics.>
Acceptance Criteria (field):
  - bullet list, one per behavior
Meta: optional
```

Maintenance/platform/debt work with no end-customer actor. Tests that reviewers
can judge business value of enabler work (and that "no end user" alone is not
a finding). Self-contained per scenario — not a rendering of the user-actor
canonical stories (see the matrix section).

## T6 — Free text

```text
Title:       whatever the author wrote (can be terse or cryptic)
Description:
  one or more plain paragraphs, no sections, no conventions;
  links and details inline where they happen to appear
Acceptance Criteria (field): (usually empty; if present, unstructured)
Meta: none
```

No template at all. Not "bad" by definition — the content may be complete and
precise, but the reviewer has to work it out from raw prose. T6 renderings
must still contain every canonical fact (see the canonical content model).

## Usage in the current dataset (first column of the matrix)

All six scenarios are authored in T1 first (the baseline column), then
duplicated across T2–T6 in later increments. Stories carry **no Effort**
(review happens pre-estimation, in the backlog) and live in the backlog
iteration.
