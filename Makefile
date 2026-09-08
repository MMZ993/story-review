# Home-phase Makefile skeleton (Phase 0). Targets for later phases are stubs
# and are filled in when their units exist (per docs-local/development-plan.md).

PROJECT_ID ?= $(shell sed -nE 's/^export PROJECT_ID="?([^"]+)"?.*/\1/p' infra/envs/home.env 2>/dev/null)
REGION     ?= europe-west4
SMOKE_MODEL ?= gemini-2.5-flash

.PHONY: help smoke-vertex spike-connectivity-test review-schemas-test dataset-test compose-up compose-down terraform-plan terraform-apply db-pause db-resume db-status

# Fails the target early if PROJECT_ID could not be resolved from home.env.
define guard-project
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "ERROR: PROJECT_ID is not set — check infra/envs/home.env" >&2; exit 2; \
	fi
endef

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

smoke-vertex: ## Phase 0 exit check: local ADK agent -> Gemini via Vertex AI (ADC)
	GOOGLE_GENAI_USE_VERTEXAI=true \
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) \
	GOOGLE_CLOUD_LOCATION=$(REGION) \
	SMOKE_MODEL=$(SMOKE_MODEL) \
	uv run --with google-adk python scripts/smoke_vertex.py

spike-db-bootstrap: ## Phase 1 spike: one-time DB admin bootstrap (needs SPIKE_DB_PASSWORD)
	uv run --with-requirements spikes/connectivity/sql/requirements.lock \
		python spikes/connectivity/sql/admin_apply.py

spike-connectivity-test: ## Phase 1 spike: deterministic store/contract/agent-probe tests
	uv run --with-requirements spikes/connectivity/tests/requirements.lock \
		python -m pytest spikes/connectivity/tests -q --asyncio-mode=auto

review-schemas-test: ## Phase 2: deterministic shared-schema contract tests
	cd shared/review_schemas && \
		uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable . python -m pytest tests -q

dataset-test: ## Phase 3: mock-dataset loader/validation tests (stories + expected)
	cd dataset/loader && \
		uv run --no-project --with-requirements tests/requirements.lock \
		--with-requirements requirements.lock --with-editable . \
		--with ../../shared/review_schemas python -m pytest tests -q

compose-up: ## Local development stack (Phase 4+)
	@echo "compose-up: stub — defined when MCP services land (Phase 4)"

compose-down: ## Stop the local development stack (Phase 4+)
	@echo "compose-down: stub — defined when MCP services land (Phase 4)"

terraform-plan: ## Review plan for the home environment
	terraform -chdir=infra plan -var-file=envs/home.tfvars -out=home.tfplan

terraform-apply: ## Apply the saved home plan (write action)
	terraform -chdir=infra apply home.tfplan

db-pause: ## Stop Cloud SQL instance (activation-policy NEVER) — stops compute billing
	$(guard-project)
	gcloud sql instances patch $(PROJECT_ID)-sessions \
		--activation-policy NEVER && echo "instance stopped"

db-resume: ## Start Cloud SQL instance (activation-policy ALWAYS) — takes ~1-2 min
	$(guard-project)
	gcloud sql instances patch $(PROJECT_ID)-sessions \
		--activation-policy ALWAYS && echo "instance running"

db-status: ## Show Cloud SQL instance state (read-only)
	$(guard-project)
	gcloud sql instances describe $(PROJECT_ID)-sessions \
		--format='value(state,settings.activationPolicy)'
