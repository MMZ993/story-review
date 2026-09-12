# Runbook 14 — GCP deployment & versioning proof (Phase 8)

Plan: `docs-local/plans/phase-8-gcp-deployment.md`. Decisions: D24 (+
D5/D17 dependencies). All cloud actions follow infra-rules: read-only is
agent-runnable; tier-2 (writes) owner-approved; destructive actions are
owner-run only. Evidence sanitized (`$PROJECT_ID`, placeholders) —
identifier check before any commit containing evidence.

## Increment 0 — decisions, plan, deploy-script fixes

(pending)
