# Runbook 00 — Tooling

Machine setup for the home phase. Checked 2026-09-05.

## Already present

| Tool | Version |
|---|---|
| terraform | v1.16.1 |
| make | GNU Make 4.4.1 |
| python3 | 3.14.7 |
| uv | 0.12.9 (Python dependency + venv management; poetry intentionally not used) |
| docker | 29.4.3 |
| jq | 1.8.2 |
| plantuml | 1.2026.2 (for regenerating docs/diagrams) |

## Installed for this project

```bash
# gcloud CLI, managed by mise like the rest of the toolchain
mise use -g gcloud
gcloud --version   # verify; note the components/gcloud version installed
```

## Project tooling decisions

- Python envs and dependencies via `uv` (locks in `requirements.lock` per unit per
  docs/operations/repository-layout.md; generated with `uv pip compile`).
- No poetry, no Ansible (see ../local-decisions.md D2, D3).
