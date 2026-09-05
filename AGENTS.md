# AGENTS.md — working agreement and meta context

Instructions for any coding agent working in this repository (pi sessions in
particular). This is the persistent "how we work" layer that does not belong in
`docs/` (capstone design) or `docs-local/` (home-phase documentation). Read this
file fully before acting.

## Session catch-up order (fresh session)

0. **Cloud SQL cost check**: run `make db-status` (read-only). If the instance
   is RUNNING and no work in the session needs the database, remind the owner
   to `make db-pause`. At session wrap-up, if the DB is RUNNING, remind the
   owner to pause it (`make db-pause`) unless the next session needs it live.
1. This file.
2. `.agents/HANDOFF.md` — current phase, what is done, what is next.
3. `docs-local/development-plan.md` — phased plan detail.
4. `docs-local/runbook.md` + `docs-local/runbooks/` — what has been executed and
   evidenced so far.
5. `docs-local/local-decisions.md` — home-phase decisions (D1–D5).
6. `docs/` design set — only the sections relevant to the current task; the reading
   order is in `docs/index.md`.

The git history is the authoritative record of what changed; runbooks are the
authoritative record of what was executed against Google Cloud.

## Collaboration protocol (agreed with the owner)

- **No commands behind the owner's back.** Two allowed modes only:
  1. Propose the exact commands in the chat/runbook, explain what each does and why,
     and the owner runs them and pastes output back; or
  2. The owner explicitly says "run it" / approves execution in chat, and the agent
     executes — explaining before and reporting output after.
- **Every executed environment action is codified first or immediately after**: a
  runbook entry with the exact commands, what they do, gotchas learned, and evidence
  (IDs, outputs). Nothing lives only in shell history or chat.
- **Explaining while working**: when the agent runs commands, it says what it is
  doing and why; output is reported back, not silently consumed.
- **Destructive or billing-relevant actions** (deletes, project shutdown, new
  billable resources) always require explicit confirmation first.
- **Pace**: the owner wants to learn and be able to track the commands too — prefer slower loops with
  explanation over agent-only speed.

## Task-specific rule files (load conditionally)

- [`.agents/development-rules.md`](.agents/development-rules.md) — **read before
  writing/changing application code** (Python, schemas, tests, agents,
  orchestration, TUI): doc-first, test-first, file-size and design limits,
  verification tiers, debugging, review triggers.
- [`.agents/infra-rules.md`](.agents/infra-rules.md) — **read before touching
  terraform, gcloud, or any deployment/environment action**: command tiers
  (read-only / write / destructive), plan-before-apply, IaC-only, runbook
  codification, cost awareness, gotchas learned.

## Session wrap-up

Follow the `session-wrapup` skill: every planned task accounted for, then update
`.agents/HANDOFF.md` (previous summary, verification, remaining tasks, next steps,
notes) so a fresh session catches up via this file.

### HANDOFF and git

- `.agents/HANDOFF.md` **belongs to git** — it is the catch-up document for fresh
  sessions and clones; its history doubles as a session log.
- **Before any commit, verify it is not stale**: it must reflect the current
  session's outcome (done/next/notes updated, date bumped). Never commit with a
  stale HANDOFF, and never leave it dirty between sessions.
- Fold the HANDOFF update into the session's work commit, or make a small
  standalone `chore:` commit at wrap-up.
- Note: the owner's global gitignore excludes `.agents/` by default; in this
  repo it is **force-tracked**. Once a file is tracked, ignore rules stop applying
  to it — but any *new* file under `.agents/` must be added with
  `git add -f .agents/<file>`.

## Secrets and identifiers

- Project IDs, billing account, budget IDs and similar identifiers are NOT secrets,
  but they are kept out of git per the convention in
  `docs/operations/connectivity-identity.md`.
- They live only in the gitignored `infra/envs/home.env`. Runbooks and commands use
  shell variables (`$PROJECT_ID`, `$BILLING_ACCOUNT`, ...) and start with
  `source infra/envs/home.env`.
- Never commit identifiers, SA keys, tokens, or `*.env` files. ADC
  (`~/.config/gcloud/application_default_credentials.json`) is the credential; no
  key files.

## Repository conventions

- Docs-driven: `docs/` is the authoritative capstone design; changes to
  implementation must follow it, and deviations must be recorded in
  `docs-local/local-decisions.md` (or a design change in `docs/` if fundamental).
- `docs-local/` holds home-phase material only; `docs/` stays company-neutral.
- Diagrams: Mermaid inline in docs; ASCII sequence diagrams are generated from
  `design/diagrams/*.puml` with `plantuml -ttxt`.
- Python tooling: `uv` (venvs, locks — `requirements.lock` per unit, generated via
  `uv pip compile`). No poetry. No Ansible.
- Commits: conventional style (`type: lowercase imperative description`), atomic,
  explicit paths only (`git add <path>`, never `git add .`); commit only when the
  owner asks. Amend on request is fine.
- Branch `docs/initial-frozen` = the frozen initial design; diff against it to see
  later documentation changes.

## Safety rules (explicit, non-negotiable)

- **Destructive commands are run by the user only — in any domain, not just git.**
  The agent never executes destructive operations itself; it proposes the exact
  command and the owner runs it. Destructive includes, among others:
  - git: force push, resets, branch deletion, anything rewriting history;
  - Google Cloud: project/resource/service deletion, `terraform destroy`, IAM
    removals, database deletion;
  - filesystem: recursive deletion, overwriting files outside this repository;
  - databases: destructive migrations, table/data drops.
- **Git history rewrite only on explicit user request and approval**, and limited
  to the most recent commit(s) made in the current session (e.g. `--amend` of this
  session's last commit). No rebases or resets of older history, ever.
- **`git push` is prohibited.** The user pushes. Always.

## Current state

Kept in [.agents/HANDOFF.md](.agents/HANDOFF.md) — a living document updated at every
phase transition and material progress point. Update it before ending a session.
