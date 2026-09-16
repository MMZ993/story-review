# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. This file stays **short**: current phase, recent sessions, active
deferred work, next steps, and standing operational notes. Historical detail
lives in its authoritative homes — runbooks (`docs-local/runbooks/`, the record
of what was executed), `docs-local/local-decisions.md` (D1–D29),
`docs-local/plans/`, `docs-local/development-plan.md`, and this file's own
git history (the session log). Do not let this file grow back into an archive.

Last updated: 2026-09-16 (dev server; webui mobile fix deployed live +
HANDOFF condensed).

## Next Session

### Remaining Tasks

- **Phase 9 increments 3–5** per `docs-local/plans/phase-9-evaluation.md`
  (all remaining failures PROMPT-class, Runbook 15 §Increment 2 run 5):
  delegation calibration (single-side where expected; never `both` in
  unresolvable dialogue turns; conversational resolution instead of
  delegation in conflicting/hidden-conflict), severity calibration
  (blockers everywhere vs info/major ceilings), open issues never empty at
  acceptance, conflict detection (synthesis `conflicts: []` on every case),
  facilitator story-MCP tool calls on comment scenarios, synthesis
  inputs-echo corruption (stochastic).
- Deferred Phase-8 review minors (Runbook 14 §Increment 7): env-pointer/
  version runtime cross-check; compaction checkpoint-boundary +
  genai-Content test nits; per-call summarizer client.
- One live test session (`sess-8031e95b…`, story-09) left active on dev —
  its x-user-id wasn't persisted, cannot be abandoned from here (carry-over
  from increment 7).
- D5 engine prune (owner-run) — remaining Phase-8 cleanup.

### Next Steps

1. Phase 9 increment 3 — judged full set + prompt tuning loop.

Standing notes: dev Cloud SQL RUNNING (owner request — leave up); local
compose stack intentionally up (serves pre-mobile-fix webui image;
`make agents-compose-up` to refresh). Owner pushes main (`05592e8` mobile
fix + wrap-up commit pending push).

### Verification and Review

This session (webui mobile fix): `make webui-test` pytest **25** + vitest
**89**; `git diff --check` clean; deployed image `20260916-0511-05592e8`
(revision `webui-00003-bhv`, 100% traffic); public domain health 200 with
the new CSS live. Evidence: Runbook 13 §Mobile picker fix. Presentation-only
CSS change — no review due, no new test applies.

Prior session (Phase 9 increment 2): dataset **37 passed** (+1); evaluation
**90 passed** (+3); run 5 full t1 **DATASET bucket empty** (engineering-weak
0 failures; unresolvable 11→3); ADO enriched + re-exported. Evidence:
Runbook 15 §Increment 2. Open doc item unchanged (evaluation-tests.md
finding-key wording).

## Where we are

- **Phase 9 (Evaluation suite & tuning) IN PROGRESS** — increments 0–2 done
  (judge skeleton, deterministic assertion engine, dataset tuning pass);
  increments 3–5 remain. Plan: `docs-local/plans/phase-9-evaluation.md`;
  evidence: Runbook 15; D29 (demo deferred until suite passes; story and
  prompt tuning in scope).
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

**Webui mobile fix + HANDOFF condensation (2026-09-16, dev server;
cloud actions owner-approved "please run it"; detail: Runbook 13
§Mobile picker fix):** owner-reported defect — story list below the fold on
phones with the confirm button at top. Minimal owner-chosen fix:
`#confirm-story` fixed bottom-right in the mobile media query, picker
bottom padding (CSS-only, commit `05592e8`). Deployed via
`deploy/cloud-run/webui/deploy.sh` (image tag maps to the commit); public
domain verified. HANDOFF condensed to this file (history preserved in git).

**Phase 9 increment 2 — dataset tuning (2026-09-15, dev server; detail:
Runbook 15 §Increment 2):** representativeness walk clean (8×10);
D-a unresolvable artifacts unpinned + capture-based conflict pinning
(evaluation 90, dataset 37); D-b ADO enrichment + re-export
(JSON-Patch-body-is-an-array gotcha); run 5: DATASET bucket empty —
first fully passing case; remainder all PROMPT-class for increment 3.

Detail for all earlier sessions: `git log --follow -- .agents/HANDOFF.md`,
the per-phase runbooks, and `docs-local/local-decisions.md` (D1–D29 with
amendments).
