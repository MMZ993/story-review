# Home-phase Makefile skeleton (Phase 0). Targets for later phases are stubs
# and are filled in when their units exist (per docs-local/development-plan.md).

PROJECT_ID ?= $(shell sed -nE 's/^export PROJECT_ID="?([^"]+)"?.*/\1/p' infra/envs/home.env 2>/dev/null)
REGION     ?= europe-west4
SMOKE_MODEL ?= gemini-2.5-flash

.PHONY: help smoke-vertex spike-connectivity-test compose-up compose-down terraform-plan terraform-apply

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

compose-up: ## Local development stack (Phase 4+)
	@echo "compose-up: stub — defined when MCP services land (Phase 4)"

compose-down: ## Stop the local development stack (Phase 4+)
	@echo "compose-down: stub — defined when MCP services land (Phase 4)"

terraform-plan: ## Review plan for the home environment
	terraform -chdir=infra plan -var-file=envs/home.tfvars -out=home.tfplan

terraform-apply: ## Apply the saved home plan (write action)
	terraform -chdir=infra apply home.tfplan
