# HANDOFF — living project state

Linked from AGENTS.md; updated at every phase transition and material progress
point. This file stays **short**: current phase, recent sessions, active
deferred work, next steps, and standing operational notes. Historical detail
lives in its authoritative homes — runbooks (`docs-local/runbooks/`, the record
of what was executed), `docs-local/local-decisions.md` (D1–D29),
`docs-local/plans/`, `docs-local/development-plan.md`, and this file's own
git history (the session log). Do not let this file grow back into an archive.

Last updated: 2026-09-18 (**D35 shipped**: reviewer severity fence +
suite tolerance; run-28 t1 = **2/10 with clean + comments-benign
passing for the first time**; remaining failures are non-severity
classes. Detail: Runbook 15 §Increment 3 part 8; design: data-flow.md
§Reviewer output fence, evaluation-tests.md §severity tolerance,
local-decisions D35.)

## Next Session

### Remaining Tasks

- **Synthesis conflict-emission variance** (top remaining failure
  class after D35): designed conflicts C-1/C-2 not emitted
  (partial-resolution, hidden-conflict) or dropped mid-arc
  (unresolvable v2/v3) — synthesis prompt/gate tuning, not severity.
- **Facilitator routing drift**: invoke `both`/`none` instead of the
  single designed perspective (engineering-weak, comments-clarify,
  hidden-conflict, partial-resolution turn 3).
- **Unfenced minors keep open issues**: a tolerated minor still blocks
  the readiness finalize (comments-complete-engineering) — candidate:
  extend the D34 opening fence / readiness gate to auto-resolve
  minor-only open issues.
- hidden-conflict severity inflation persists by design (the story must
  stay contradictory) — prompt calibration territory only.
- D35 live deployment: round-13 reviewer prompts + fence run locally
  only; AE engines + orchestration revision NOT yet redeployed.
- Deferred Phase-8 review minors (Runbook 14 §Increment 7): env-pointer/
  version runtime cross-check; compaction checkpoint-boundary +
  genai-Content test nits; per-call summarizer client.
- Pre-existing failing test (flagged 2026-09-18): `agents/facilitator
  tests/test_agent.py::test_config_is_pinned_and_immutable` expects
  gemini-2.5-flash but config is pro (stale since the D13 amd-2 bump).
- One live test session (`sess-8031e95b…`, story-09) left active on dev —
  its x-user-id wasn't persisted, cannot be abandoned from here (carry-over
  from increment 7).
- D5 engine prune (owner-run) — remaining Phase-8 cleanup; grows with the
  superseded AE engines from the run-25 session.

### Next Steps

1. Tackle synthesis conflict emission (prompt/gate tuning), then
   facilitator routing drift; rerun t1 (`bash tmp/run28-chunk.sh
   <scenario>` — includes `--tolerance minor-over-info`).
2. When t1 stabilizes: redeploy round-13 reviewer engines + the fence
   orchestration revision to live (D35 deployment), then consider
   `JUDGE=1`.
3. Standing note: the plan's documented stochastic-instability rerun
   remains valid for blips.

Standing notes: dev Cloud SQL RUNNING (owner request — leave up; check
`make db-pause` at next wrap-up if not needed); local compose stack
rebuilt with D35 fence + round-13 prompts (ahead of live — live still
on `4c81133`); everything through `4c81133` pushed except this
session's changes (uncommitted).
Live probe sessions left active: `sess-06fdb260…` (D34 verify, user id
in /tmp/d34-verify-user.txt, abandonable), `sess-135fa2a8…` (user id in
/tmp/r12b-verify-user.txt, abandonable) and the known increment-7
`sess-8031e95b…`; failed-create attempts leave no sessions. Superseded
AE engines retained — fold into the D5 prune list: reviewers/synthesis
`6a73636`… are current; old facilitators `6618…`, `7322…`
(`5452be1`), `6251392106976247808` (`747d9d1`) are superseded by
`2601224608992460800` (`facilitator-4c81133`). Probe nit:
tmp/probe_facilitator.py's summary print uses dict access on pydantic
models (fails after the render — harmless; fix when convenient).

### Verification and Review

This session (run 25 + GCP deploys): round-12 prompts baked + validated —
**0/9, systematic reviewer regression**; A/B (reviewers back to round-11)
PASS; round-12b validated (clean PASS) and committed. GCP: four `6a73636`
engines + orchestration deployed; stale GCS story dataset synced +
mcp-story rolled; **AE facilitator opening-turn 422s found — AE runtime
lacks the corrective loop** (probe-verified; round-12c prompt deployed,
did not bind on AE); live rolled back to `facilitator-747d9d1` (D32,
live 201 verified). Owner demo walkthrough (story-01, live mixed stack):
opening turn stochastically minted B-1 major + C-1 conflict (reviewer
calibration drift, same class as run-24/25 — severity is nowhere
hard-validated); one PO scope-fence clarification resolved them; info
findings (B-3/E-*) needed a second explicit-decision PO turn — the
pre-round-12 facilitator keeping info findings open, as expected (D32
gap). Clean story demo today = story-01 + 1–2 PO turns. Evidence:
Runbook 15 §Increment 3 parts 5–6.

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

**D35 severity fence + dataset round (2026-09-18, dev server; detail:
Runbook 15 §Increment 3 part 8):** run-26 triage → five ADO story
enrichments (ids 10/17/57/58/59, comment ids 507000–2, revs 5/3;
canonical-facts + comments-spec updated), unresolvable expected ceiling
→ blocker + C-1 kind fixed to schema-expressible, prompt round 13
(perspective discipline + re-review downgrade rule). Run 27 proved the
whack-a-mole conclusion; owner chose "both": **D35** — orchestration
`reviewer_output_fence.py` (scope-settlement drop + re-review clamp,
overlap-coefficient thresholds calibrated on real captures, structured
events, both invocation choke points) + runner `--tolerance
minor-over-info`. Fixed a live TimedResult 500 in the fence wiring;
pinned capture regressions as committed fixtures. Tests: orchestration
**231**, evaluation unit **113**, loader 37. **Run 28 = 2/10: t1/clean
and t1/comments-benign pass for the first time.** Remaining: synthesis
conflict emission, routing drift, unfenced-minor open issues. Local
stack ahead of live (D35 + round-13 not yet deployed).

**D34 deploy + run-26 (2026-09-17, dev server; detail: Runbook 15
§Increment 3 part 7):** deployed `facilitator-4c81133` (engine
`2601224608992460800`, smoke PASS) and orchestration image
`20260917-2039-4c81133` (revision `orchestration-00037-m4c`, env
verified, health green); AE probe shows the P1 fence; live story-01
flow-1 → **201** (was the deterministic 422) — live converged off the
mixed stack. Local compose rebuilt to HEAD. run-26 t1 chunk A (4
cases) 0/4 — all on the known reviewer severity drift (B-1 major + C-1
minted on clean; facilitator behaved per D34); owner-directed clean
rerun **PASS**. Owner then directed the remaining six t1 scenarios
(one template only; t2–t6 untouched): 0/6 — same over-severization
class at worse amplitude (blocker inflation on hidden-conflict and
unresolvable, C-1 mis-kinded), full suite **0/10**, no D34 failure,
no 422. Chunk logs `/tmp/run26-chunkB.log` + `/tmp/run26-chunkC.log`.
Nothing committed this session (runbook + HANDOFF updates pending).

**D32 → D34 design decision + local implementation (2026-09-18, dev
server):** with the owner, reframed the D32 root cause as a prompt-rule
collision (round-12 resolve-info/minor vs positional no-turn-1-
resolutions) and adopted design change **D34** (P1): turn-1 resolutions
are now severity-fenced (resolved info/minor synthesis findings only,
mentioned to the PO) instead of forbidden — docs touched
(`agents.md`, `schemas.md`), facilitator prompt simplified,
`validate_turn_output` reimplemented (`_validate_opening_fence`). AE-side
corrective loop = orchestration (option C, D25 amendment): new
`orchestration/orchestration/ae_turn_validation.py` mirror +
bounded loop in `AeFacilitatorClient.invoke` (≤2, exhaustion →
DELEGATION_VALIDATION 422, `corrective_reprompts` surfaced; corrective
messages carry the turn marker so D25 reconciliation stays attributable);
`flows._assert_opening_turn` backstop reuses the mirror. Independent
read-only review addressed (corrective-failure reconciliation, third-copy
fence removal, schema-invalid corrective replies fold into the loop, test
gaps). Verification: `make agent-kit-test` 165 passed, `make
orchestration-test` 218 passed, `make evaluation-unit-test` 104 passed;
pre-existing facilitator skeleton test failure flagged (see Remaining).
**Nothing deployed yet.**

**Phase 9 increment 3, parts 5–6 — run 25 regression, round-12b, GCP
deploy + AE corrective-loop gap (2026-09-17, dev server; detail:
Runbook 15 §Increment 3 parts 5–6):** see above. Earlier increment-3
parts and sessions: git history of this file.

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
