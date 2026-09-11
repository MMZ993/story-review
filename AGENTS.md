# AGENTS.md — working agreement and meta context

Instructions for any coding agent working in this repository (pi sessions in
particular). This is the persistent "how we work" layer that does not belong in
`docs/` (capstone design) or `docs-local/` (home-phase documentation). Read this
file fully before acting.

## Session catch-up order (fresh session)

0. **Local environment**: try to read [WORKING_ENVIRONMENT.md](WORKING_ENVIRONMENT.md)
   if it exists (it may not — it is local-only and gitignored). It describes
   the current machine's working environment: what is available (credentials,
   terraform state, env files, tools) and what is not, and any environment-specific
   rules. **Never commit, stage, or delete this file** — it relates only to the
   computer it lives on. If absent, assume nothing about the environment beyond
   this AGENTS.md.
1. **Cloud SQL cost check** (only if the local environment has cloud access): run
   `make db-status` (read-only). If the instance is RUNNING and no work in the
   session needs the database, remind the owner to `make db-pause`. At session
   wrap-up, if the DB is RUNNING, remind the owner to pause it (`make db-pause`)
   unless the next session needs it live.
2. This file.
3. `.agents/HANDOFF.md` — current phase, what is done, what is next.
4. `docs-local/development-plan.md` — phased plan detail.
5. `docs-local/runbook.md` + `docs-local/runbooks/` — what has been executed and
   evidenced so far.
6. `docs-local/local-decisions.md` — home-phase decisions (D1–D5).
7. `docs/` design set — only the sections relevant to the current task; the reading
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
  orchestration, Web UI): doc-first, test-first, file-size and design limits,
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
- **Evidence must be sanitized before it enters git.** Pasted outputs in runbooks,
  HANDOFF, commits, or issues must not contain the real project ID or other
  persistent identifiers — replace them with the shell-variable form
  (`$PROJECT_ID`, `$PROJECT_ID-sessions`, ...) even inside "verbatim" output
  blocks. Random resource IDs (revision hashes, engine IDs, correlation IDs) of
  already-torn-down disposable resources are acceptable, but prefer placeholders
  (`<service-url>`, `<engine-id>`) for anything resolvable.
- Never commit identifiers, SA keys, tokens, or `*.env` files. ADC
  (`~/.config/gcloud/application_default_credentials.json`) is the credential; no
  key files.

## Docs-first rule (standing instruction)

Before acting on any task — code, infra, tests, or docs changes — consult the
relevant sections of `docs/` (authoritative design) and `docs-local/`
(home-phase reality: development plan, runbooks, local decisions). Code and
infrastructure follow the docs, never the reverse. The catch-up reading above
is the session-start baseline, not a substitute: a mid-session task in an area
not yet read requires looking it up in the docs first.

If you find an inconsistency — doc vs doc, or doc vs reality — do **not**
silently work around it and do **not** silently fix it. Raise it with the
owner, agree the resolution, then record it: implementation deviations in
`docs-local/local-decisions.md`; fundamental design changes as a change in
`docs/` itself (with the owner's approval).

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
