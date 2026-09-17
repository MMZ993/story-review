# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. This file stays **short**: current phase, recent sessions, active
deferred work, next steps, and standing operational notes. Historical detail
lives in its authoritative homes — runbooks (`docs-local/runbooks/`, the record
of what was executed), `docs-local/local-decisions.md` (D1–D29),
`docs-local/plans/`, `docs-local/development-plan.md`, and this file's own
git history (the session log). Do not let this file grow back into an archive.

Last updated: 2026-09-17 (dev server; run 25: round-12 reviewer edits
regressed severity (0/9, clean failed twice); A/B isolated causation;
round-12b validated (round-11 reviewers + round-12 facilitator/synthesis,
clean PASS) and committed (D31); GCP agents redeployed from round-12b.
Judge still not exercised. Detail: Runbook 15 §Increment 3 part 5.

## Next Session

### Remaining Tasks

- **Phase 9 increment 3 (continue)**: run 25 evidence recorded
  (Runbook 15 §Increment 3 part 5; D31): round-12b is the validated
  prompt state and the committed/deployed baseline. Remaining: full t1
  suite on round-12b in chunks of ≤4 scenarios; if green holds, add
  `JUDGE=1`; re-attempt reviewer re-review-scope discipline as a
  smaller additive edit (without the severity rewording).
- Deferred Phase-8 review minors (Runbook 14 §Increment 7): env-pointer/
  version runtime cross-check; compaction checkpoint-boundary +
  genai-Content test nits; per-call summarizer client.
- One live test session (`sess-8031e95b…`, story-09) left active on dev —
  its x-user-id wasn't persisted, cannot be abandoned from here (carry-over
  from increment 7).
- D5 engine prune (owner-run) — remaining Phase-8 cleanup.

### Next Steps

1. Continue increment 3 on round-12b: full t1 suite in chunks of ≤4
   scenarios via `bash tmp/run25-chunk.sh <scenario>` (bg-job cap
   ≈45 min); if green holds, add `JUDGE=1`.
2. Standing note: per plan risk list, a case failing solely on
   demonstrated stochastic instability may get one documented rerun
   (both outputs kept); consider codifying in the runner or runbook
   practice if blips persist.

Standing notes: dev Cloud SQL RUNNING (owner request — leave up); local
compose stack intentionally up (run-23 prompt images); all increment-3
part-2 work pushed (through `4a88656`).

### Verification and Review

This session (run 25): round-12 prompts baked + validated — **0/9,
systematic regression**: clean failed twice consecutively with minted
v1 majors; major-minting worse than run 24 across all cases. A/B test
(reviewers reverted to round-11, one clean run) PASSED — causation
confirmed. Round-12b (round-11 reviewers + round-12 facilitator/
synthesis) validated: clean PASS. D31; reviewer revert committed;
GCP agents redeployed from round-12b commit. Evidence: Runbook 15
§Increment 3 part 5.

Prior session (increment 3, part 1): evaluation unit tests **104
passed** (+14); live runs 6–11; delegation assertion re-based on
executed evidence (D13 amendment 3 context).

Prior session (webui mobile fix): `make webui-test` pytest **25** + vitest
**89**; deployed image `20260916-0511-05592e8`; public domain verified.
Evidence: Runbook 13 §Mobile picker fix.

## Where we are

- **Phase 9 (Evaluation suite & tuning) IN PROGRESS** — increments 0–2
  done; increment 3 in progress (judge wired + trend; D13 amendment 2
  pro bump; 6 prompt rounds; 3-case subset near-green). Plan:
  `docs-local/plans/phase-9-evaluation.md`; evidence: Runbook 15;
  D29 (demo deferred) + D13 amendments 2–3.
- **Phase 8 (Real GCP deployment & versioning proof) COMPLETE** — everything
  live on GCP (webui/orchestration/MCP on Cloud Run, four AE agents, Cloud
  SQL, monitoring); system reachable at `https://story-review.mmz.sh`.
  Runbook 14; D24–D28.
- **Phase 7 (Web UI) COMPLETE** — Runbook 13; D16–D22.
- **Phase 6 (Orchestration) COMPLETE** — Runbook 12; D15 + amendments.
- **Phase 5 COMPLETE** — Runbook 11; D13/D14. **Phase 4 COMPLETE** —
  Runbook 10; D10–D12. **Phase 3 COMPLETE** — Runbooks 08–09.
  **Phase 2 COMPLETE** — Runbook 07. **Phase 1 complete** — Runbook 06.
- Docs design frozen on `docs/initial-frozen`; home-phase docs in
  `docs-local/`. Remote `origin` = private GitLab
  (`mmz-personal/capstone-project`); **owner pushes** (main +
  `docs/initial-frozen`).

## Previous Session Summary

**Phase 9 increment 3, part 5 — run 25 regression + round-12b (2026-09-17,
dev server; detail: Runbook 15 §Increment 3 part 5):** see above. Earlier
increment-3 parts and sessions: git history of this file.

**Phase 9 increment 3, part 2 (2026-09-16, dev server; detail: Runbook 15
§Increment 3 part 2):** prompt rounds 8–10 (engineering severity
procedure consolidation + few-shot calibration, synthesis conflict
materiality + pre-emit gates, facilitator decision/acceptance rules);
story-01 ADO enrichment (email-failure scope, rev 6); ADK `{id}`
prompt-templating gotcha. Runs 12–23: clean reached the stochastic noise
floor and **PASSED in the full suite**; run 23 = 1/10 with regressions
on comments scenarios, two routing clusters, unresolvable, and a
hidden-conflict 422. Judge still not exercised.

**Phase 9 increment 3, part 1 (2026-09-16, dev server):** judge stage
wired (one call per deterministic-passing case; trend; `--judge`/
`--smoke`/`--label`). Suite delegation assertion re-based on executed
evidence. Owner-approved model bump (D13 amd 2): reviewers +
facilitator on gemini-2.5-pro. Six prompt rounds; 3-case subset
near-green.

**Webui mobile fix + HANDOFF condensation (2026-09-16):** CSS-only fix
(`05592e8`), deployed, public domain verified. Detail: Runbook 13
§Mobile picker fix.

Detail for all earlier sessions: `git log --follow -- .agents/HANDOFF.md`,
the per-phase runbooks, and `docs-local/local-decisions.md` (D1–D29 with
amendments).
