# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. This file stays **short**: current phase, recent sessions, active
deferred work, next steps, and standing operational notes. Historical detail
lives in its authoritative homes — runbooks (`docs-local/runbooks/`, the record
of what was executed), `docs-local/local-decisions.md` (D1–D29),
`docs-local/plans/`, `docs-local/development-plan.md`, and this file's own
git history (the session log). Do not let this file grow back into an archive.

Last updated: 2026-09-16 (dev server; Phase 9 increment 3 in progress —
judge wired, D13 model bump, 6 prompt-tuning rounds; detail in Runbook 15
§Increment 3).

## Next Session

### Remaining Tasks

- **Phase 9 increment 3 (continue)**: get t1 deterministic-green, then
  first live judged run + `evaluation-smoke`; remaining clusters after
  run 11 (Runbook 15 §Increment 3): engineering-reviewer severity on
  `clean` (stochastic majors: order-API fetch failure, audit-log/alerting
  deps), `business-weak` engineering minors (ceiling info) + 2 open at
  final, `conflicting` facilitator keeps definitional majors open after
  the PO decision → no finalize. Then increments 4 (dev-mode run) and 5
  (close) per `docs-local/plans/phase-9-evaluation.md`.
- Deferred Phase-8 review minors (Runbook 14 §Increment 7): env-pointer/
  version runtime cross-check; compaction checkpoint-boundary +
  genai-Content test nits; per-call summarizer client.
- One live test session (`sess-8031e95b…`, story-09) left active on dev —
  its x-user-id wasn't persisted, cannot be abandoned from here (carry-over
  from increment 7).
- D5 engine prune (owner-run) — remaining Phase-8 cleanup.

### Next Steps

1. Continue increment 3 prompt loop from run-11 evidence (Runbook 15
   §Increment 3); re-run the 3-case subset, then full t1, then JUDGE=1.

Standing notes: dev Cloud SQL RUNNING (owner request — leave up); local
compose stack intentionally up (serves pre-mobile-fix webui image;
`make agents-compose-up` to refresh). Owner pushes main (`05592e8` mobile
fix + wrap-up commit pending push).

### Verification and Review

This session (increment 3, in progress): evaluation unit tests **104
passed** (+14: judge stage, trend, judge wiring, evidence-based
delegation assertion); dataset **37 passed**; `git diff --check` clean;
no orchestration changes. Live runs 6–11 (owner-approved spend)
evidenced in Runbook 15 §Increment 3; compose stack UP with pro
reviewers+facilitator (D13 amendment 2); delegation assertion re-based
on executed evidence (D13 amendment 3 context). Judge stage wired but
not yet exercised live.

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

**Phase 9 increment 3, part 1 (2026-09-16, dev server; detail: Runbook 15
§Increment 3):** judge stage wired into the runner (one call per
deterministic-passing case; trend report; `--judge`/`--smoke`/`--label`;
`make evaluation-test JUDGE=1`; `evaluation-smoke` = t1 + judged clean).
Root-caused a suite CODE bug: delegation assertions read
`TurnRecord.delegation` (by design the post-summary next-turn intent) —
re-based on executed evidence (review versions ≥2 +
`based_on_extra_context`); business-weak delegation now passes. Owner-
approved model bump (D13 amd 2): reviewers + facilitator on
gemini-2.5-pro. Six prompt-tuning rounds: MCP evidence fixed, conflicts
detected+resolved on `conflicting`, severities/open-issues much reduced;
remaining: engineering severity on `clean` (stochastic),
`business-weak` minors, `conflicting` finalize. Judge stage not yet live.

**Webui mobile fix + HANDOFF condensation (2026-09-16):** CSS-only fix
(`05592e8`), deployed, public domain verified. Detail: Runbook 13
§Mobile picker fix.

Detail for all earlier sessions: `git log --follow -- .agents/HANDOFF.md`,
the per-phase runbooks, and `docs-local/local-decisions.md` (D1–D29 with
amendments).
