# Runbook 01 — gcloud setup (trial account)

All commands use shell variables loaded from the gitignored `infra/envs/home.env`:

```bash
source infra/envs/home.env   # from the repo root, once per shell
```

That file holds the real identifiers (project, billing account, budget); this
runbook stays shareable. It is the only place identifiers live outside gcloud's
own config.

Status: DONE (2026-09-05). Evidence at the bottom.

## 1. Authenticate (interactive — browser)

```bash
gcloud auth login                        # user login
gcloud auth application-default login    # ADC — used by local ADK/Vertex, terraform, compose
```

Learned:
- The first ADC attempt failed with "scope not consented" — you MUST tick the
  consent checkboxes on the Google login page; otherwise re-run the command.
- ADC lands in `~/.config/gcloud/application_default_credentials.json` (standard
  location; all Google libraries look there — nothing to change).
- Consumer/trial accounts get a "no quota project" warning after login — fix with:

```bash
gcloud auth application-default set-quota-project "$PROJECT_ID"
```

Verify:

```bash
gcloud auth list                                        # shows active account
gcloud auth application-default print-access-token      # succeeds = ADC OK
```

## 2. Project config (local gcloud config, not exported env vars)

```bash
gcloud config set project "$PROJECT_ID"
gcloud config set compute/region "$REGION"
gcloud config list
```

Learned: setting compute/region triggers a one-time prompt to enable
`compute.googleapis.com` — answer N; APIs get enabled deliberately via terraform
(runbook 02), never ad-hoc from CLI prompts.

## 3. Billing + budget alert

```bash
gcloud billing accounts list                              # -> BILLING_ACCOUNT in home.env
gcloud billing projects describe "$PROJECT_ID"            # billingEnabled: True
```

Budget API must be enabled on the project first (one-off):

```bash
gcloud services enable billingbudgets.googleapis.com
```

Then create the alert at 80% of trial credits:

```bash
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT" \
  --display-name=trial-80pct \
  --budget-amount=1114PLN \
  --filter-projects=projects/"$PROJECT_ID" \
  --threshold-rule=percent=0.8
```

Learned:
- `--budget-file` (from a JSON file) does **not** exist in current gcloud — use the
  individual flags above.
- The budgets call fails with SERVICE_DISABLED for ~a minute after enabling the API
  (propagation); just wait and retry.
- The created budget shows the project *number* in its filter even when the flag got
  the ID — gcloud resolves it; expected.
- List/verify with `gcloud billing budgets list --billing-account="$BILLING_ACCOUNT"`.

## 4. Dedicated project (replaces the auto-created default)

`projects create` has no billing flag — linking is a separate step:

```bash
gcloud projects create "$PROJECT_ID" --name="Capstone Story Review"
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
gcloud billing projects describe "$PROJECT_ID"    # billingEnabled: True
```

Switch everything over to the new project:

```bash
gcloud config set project "$PROJECT_ID"
gcloud auth application-default set-quota-project "$PROJECT_ID"
```

Budgets are effectively immutable — delete the old one and recreate filtered on the
new project (enable the Budget API on the new project first; same ~1 min propagation
delay before create works):

```bash
gcloud services enable billingbudgets.googleapis.com
# ...wait ~1 min...
gcloud billing budgets delete "$(gcloud billing budgets list --billing-account="$BILLING_ACCOUNT" --format='value(budgetId)' --filter='displayName=trial-80pct')" \
  --billing-account="$BILLING_ACCOUNT" --quiet
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT" \
  --display-name=trial-80pct \
  --budget-amount=1114PLN \
  --filter-projects=projects/"$PROJECT_ID" \
  --threshold-rule=percent=0.8
```

## Evidence

- [x] `gcloud auth login` — active account confirmed
- [x] ADC token prints OK (after retry with consent); quota project set to
      `$PROJECT_ID`
- [x] Dedicated project created; billing linked (`billingEnabled: true`)
- [x] gcloud config (project, region) + ADC quota project point at `$PROJECT_ID`
- [x] Budget `trial-80pct` recreated on the dedicated project (old budget deleted);
      ID recorded as `BUDGET_ID` in `infra/envs/home.env`
