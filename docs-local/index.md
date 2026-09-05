# Local Development Documentation (home phase)

Documentation for the private, at-home development phase on a personal Google Cloud
trial account. These files complement `docs/` (the authoritative capstone design) and
do not replace it. Where the two differ, `docs/` describes the target/company setup
and this folder describes the home-phase variant and its promotion path.

## Contents

- [Local development decisions](local-decisions.md) — trial-account stance,
  Terraform/script split, pipeline deferral, differences from `docs/`.
- [Development plan](development-plan.md) — phased high-level plan (scope, exit
  criteria, cost notes); the basis for per-phase implementation plans.
- [Runbook](runbook.md) — living local dev and deploy procedures; grows as phases
  complete.

## Status convention

Phases in `development-plan.md` move through **planned → in progress → done**,
with the exit-criteria evidence noted inline (command output, screenshot path, or
correlation ID). The plan is deliberately one level above implementation; each phase
gets its own implementation plan before work starts.
