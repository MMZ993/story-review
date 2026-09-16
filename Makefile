# Home-phase Makefile skeleton (Phase 0). Targets for later phases are stubs
# and are filled in when their units exist (per docs-local/development-plan.md).

PROJECT_ID ?= $(shell sed -nE 's/^export PROJECT_ID="?([^"]+)"?.*/\1/p' infra/envs/home.env 2>/dev/null)
REGION     ?= europe-west4
SMOKE_MODEL ?= gemini-2.5-flash
# Port defaults mirror deploy/env/.env (the compose stack's own config);
# both must agree when ports are changed.
_story_port := $(shell sed -nE 's/^STORY_PORT=([0-9]+).*/\1/p' deploy/env/.env 2>/dev/null)
_artifact_port := $(shell sed -nE 's/^ARTIFACT_PORT=([0-9]+).*/\1/p' deploy/env/.env 2>/dev/null)
_report_port := $(shell sed -nE 's/^REPORT_PORT=([0-9]+).*/\1/p' deploy/env/.env 2>/dev/null)
STORY_PORT     ?= $(if $(_story_port),$(_story_port),8101)
ARTIFACT_PORT  ?= $(if $(_artifact_port),$(_artifact_port),8102)
REPORT_PORT    ?= $(if $(_report_port),$(_report_port),8103)
BUSINESS_PORT      ?= 8111
ENGINEERING_PORT   ?= 8112
SYNTHESIS_PORT     ?= 8113
FACILITATOR_PORT   ?= 8114
WEBUI_PORT         ?= 8120

.PHONY: help smoke-vertex spike-connectivity-test review-schemas-test ado-wire-test dataset-test mcp-ingress-test mcp-story-test mcp-artifact-test mcp-report-test dataset-push agent-kit-test agents-test \
	business-reviewer-adapter-test business-reviewer-live-test \
	engineering-reviewer-adapter-test engineering-reviewer-live-test \
	synthesis-adapter-test synthesis-live-test facilitator-adapter-test \
	facilitator-live-test agents-compose-up agents-compose-down \
	compose-up compose-down compose-contract-test evaluation-unit-test evaluation-test evaluation-smoke orchestration-test orchestration-flow1-live-test orchestration-turns-live-test orchestration-finalize-live-test orchestration-integration-test webui-test mcp-story-deploy mcp-artifact-deploy mcp-report-deploy mcp-story-smoke mcp-artifact-smoke mcp-report-smoke terraform-plan terraform-apply db-pause db-resume db-status

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

ado-wire-test: ## Shared ADO wire-model tests (WorkItem / WorkItemComment)
	cd shared/ado_wire && \
		uv run --no-project --with-requirements tests/requirements.lock \
		--with-requirements requirements.lock --with-editable . \
		python -m pytest tests -q

mcp-ingress-test: ## Shared ID-token ingress middleware tests (mcp_ingress)
	cd shared/mcp_ingress && \
		uv run --no-project --with-requirements tests/requirements.lock \
		--with-requirements requirements.lock --with-editable . \
		python -m pytest tests -q

dataset-test: ## Phase 3: mock-dataset loader/validation tests (stories + expected)
	cd dataset/loader && \
		uv run --no-project --with-requirements tests/requirements.lock \
		--with-requirements requirements.lock --with-editable . \
		--with ../../shared/review_schemas --with ../../shared/ado_wire \
		python -m pytest tests -q

dataset-push: ## Phase 4: publish dataset/stories to gs://$(PROJECT_ID)-story-dataset
	source infra/envs/home.env && \
		uv run --no-project --with google-cloud-storage \
		python dataset/tools/push_dataset.py

mcp-story-test: ## Phase 4: story MCP preparation + contract tests
	cd mcp_servers/story && \
		uv run --no-project --with-requirements tests/requirements.lock \
		--with-requirements requirements.lock --with-editable . \
		--with ../../shared/review_schemas --with ../../dataset/loader \
		--with ../../shared/ado_wire --with ../../shared/mcp_ingress \
		python -m pytest tests -q

mcp-artifact-test: ## Phase 4: artifact MCP storage + contract tests (fake GCS in Docker)
	container=$$(docker run -d --rm -p 127.0.0.1:9023:4443 fsouza/fake-gcs-server:latest -scheme http); \
	trap 'docker rm -f $$container >/dev/null 2>&1' EXIT; \
	for i in $$(seq 1 20); do \
		curl -sf http://127.0.0.1:9023/storage/v1/b >/dev/null && break; sleep 0.5; \
	done; \
	curl -sf http://127.0.0.1:9023/storage/v1/b >/dev/null || { echo "fake-gcs-server not ready" >&2; exit 1; }; \
	cd mcp_servers/artifact && \
	ARTIFACT_TEST_GCS_ENDPOINT=http://127.0.0.1:9023 \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable . --with-editable ../../shared/review_schemas \
		--with-editable ../../shared/mcp_ingress \
		python -m pytest tests -q

mcp-report-test: ## Phase 4: report MCP render + contract tests (fake GCS in Docker)
	container=$$(docker run -d --rm -p 127.0.0.1:9024:4443 fsouza/fake-gcs-server:latest -scheme http); \
	trap 'docker rm -f $$container >/dev/null 2>&1' EXIT; \
	for i in $$(seq 1 20); do \
		curl -sf http://127.0.0.1:9024/storage/v1/b >/dev/null && break; sleep 0.5; \
	done; \
	curl -sf http://127.0.0.1:9024/storage/v1/b >/dev/null || { echo "fake-gcs-server not ready" >&2; exit 1; }; \
	cd mcp_servers/report && \
	REPORT_TEST_GCS_ENDPOINT=http://127.0.0.1:9024 \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable . --with-editable ../../shared/review_schemas \
		--with-editable ../../shared/mcp_ingress \
		python -m pytest tests -q

agent-kit-test: ## Phase 5: shared agent support (prompt loading/hash, config) tests
	cd shared/agent_kit && \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-requirements requirements.lock --with-editable . \
		--with-editable ../review_schemas \
		python -m pytest tests -q

agents-test: ## Phase 5: deterministic agent-skeleton tests (all four agents)
	for slug in business-reviewer engineering-reviewer synthesis facilitator; do \
		cd agents/$$slug && \
		uv run --no-project --with-requirements tests/requirements.lock \
			--with-editable . --with-editable ../../shared/agent_kit \
			--with-editable ../../shared/review_schemas \
			python -m pytest tests -q || exit 1; \
		cd ../../; \
	done

business-reviewer-adapter-test: ## Phase 5: business-reviewer adapter deterministic tests (no LLM)
	cd deploy/compose/adapters/business-reviewer && \
	PROMPTS_DIR=$$PWD/../../../../prompts \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable ../../../../shared/agent_kit \
		--with-editable ../../../../shared/review_schemas \
		--with-editable ../../../../agents/business-reviewer \
		--with-editable . python -m pytest tests -q

business-reviewer-live-test: ## Phase 5: business-reviewer real-model gate (main PC, ADC + Vertex)
	source infra/envs/home.env && \
	cd deploy/compose/adapters/business-reviewer && \
	PROMPTS_DIR=$$PWD/../../../../prompts \
	AGENT_LIVE_TESTS=1 GOOGLE_GENAI_USE_VERTEXAI=true \
	GOOGLE_CLOUD_PROJECT=$$PROJECT_ID GOOGLE_CLOUD_LOCATION=$$REGION \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable ../../../../shared/agent_kit \
		--with-editable ../../../../shared/review_schemas \
		--with-editable ../../../../agents/business-reviewer \
		--with-editable . python -m pytest tests -q

engineering-reviewer-adapter-test: ## Phase 5: engineering-reviewer adapter deterministic tests (no LLM)
	cd deploy/compose/adapters/engineering-reviewer && \
	PROMPTS_DIR=$$PWD/../../../../prompts \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable ../../../../shared/agent_kit \
		--with-editable ../../../../shared/review_schemas \
		--with-editable ../../../../agents/engineering-reviewer \
		--with-editable . python -m pytest tests -q

engineering-reviewer-live-test: ## Phase 5: engineering-reviewer real-model gate (main PC, ADC + Vertex)
	source infra/envs/home.env && \
	cd deploy/compose/adapters/engineering-reviewer && \
	PROMPTS_DIR=$$PWD/../../../../prompts \
	AGENT_LIVE_TESTS=1 GOOGLE_GENAI_USE_VERTEXAI=true \
	GOOGLE_CLOUD_PROJECT=$$PROJECT_ID GOOGLE_CLOUD_LOCATION=$$REGION \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable ../../../../shared/agent_kit \
		--with-editable ../../../../shared/review_schemas \
		--with-editable ../../../../agents/engineering-reviewer \
		--with-editable . python -m pytest tests -q

synthesis-adapter-test: ## Phase 5: synthesis adapter deterministic tests (no LLM)
	cd deploy/compose/adapters/synthesis && \
	PROMPTS_DIR=$$PWD/../../../../prompts \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable ../../../../shared/agent_kit \
		--with-editable ../../../../shared/review_schemas \
		--with-editable ../../../../agents/synthesis \
		--with-editable . python -m pytest tests -q

synthesis-live-test: ## Phase 5: synthesis real-model gate (main PC, ADC + Vertex)
	source infra/envs/home.env && \
	cd deploy/compose/adapters/synthesis && \
	PROMPTS_DIR=$$PWD/../../../../prompts \
	AGENT_LIVE_TESTS=1 GOOGLE_GENAI_USE_VERTEXAI=true \
	GOOGLE_CLOUD_PROJECT=$$PROJECT_ID GOOGLE_CLOUD_LOCATION=$$REGION \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable ../../../../shared/agent_kit \
		--with-editable ../../../../shared/review_schemas \
		--with-editable ../../../../agents/synthesis \
		--with-editable . python -m pytest tests -q

orchestration-test: ## Phase 6: orchestration deterministic tests (throwaway Postgres in Docker)
	container=$$(docker run -d --rm -e POSTGRES_USER=orch \
		-e POSTGRES_PASSWORD=orch -e POSTGRES_DB=orchestration \
		-p 127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}:5432 postgres:16); \
	trap 'docker rm -f $$container >/dev/null 2>&1' EXIT; \
	for i in $$(seq 1 60); do \
		docker exec $$container pg_isready -U orch >/dev/null 2>&1 && break; sleep 0.5; \
	done; \
	docker exec $$container pg_isready -U orch >/dev/null 2>&1 || { echo "test Postgres not ready" >&2; exit 1; }; \
	DATABASE_URL=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
		deploy/cloud-sql/run-migrations.sh && \
	cd orchestration && \
	ORCH_TEST_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_GCS_PUBLIC_URL=https://gcs.invalid \
	ORCH_STORY_URL=http://story:8080/mcp ORCH_ARTIFACT_URL=http://artifact:8080/mcp \
	ORCH_REPORT_URL=http://report:8080/mcp ORCH_BUCKET=artifacts-local \
	ORCH_BUSINESS_URL=http://business:8080 ORCH_ENGINEERING_URL=http://engineering:8080 \
	ORCH_SYNTHESIS_URL=http://synthesis:8080 ORCH_FACILITATOR_URL=http://facilitator:8080 \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable . --with-editable ../shared/review_schemas \
		python -m pytest tests -q

orchestration-stack-test: ## Phase 6: stories-proxy stack tests over the real compose story MCP (needs compose-up)
	for i in $$(seq 1 60); do \
		curl -sf http://127.0.0.1:$(STORY_PORT)/health >/dev/null && break; sleep 1; \
	done; \
	curl -sf http://127.0.0.1:$(STORY_PORT)/health >/dev/null || { echo "story MCP not healthy (run make compose-up)" >&2; exit 1; }; \
	ORCH_TEST_STORY_URL=http://127.0.0.1:$(STORY_PORT)/mcp $(MAKE) --no-print-directory orchestration-test

orchestration-flow1-live-test: ## Phase 6 increment 2 live gate: one real session creation over compose (main PC; needs agents-compose-up)
	container=$$(docker run -d --rm -e POSTGRES_USER=orch \
		-e POSTGRES_PASSWORD=orch -e POSTGRES_DB=orchestration \
		-p 127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}:5432 postgres:16); \
	trap 'docker rm -f $$container >/dev/null 2>&1' EXIT; \
	for i in $$(seq 1 60); do \
		docker exec $$container pg_isready -U orch >/dev/null 2>&1 && break; sleep 0.5; \
	done; \
	docker exec $$container pg_isready -U orch >/dev/null 2>&1 || { echo "test Postgres not ready" >&2; exit 1; }; \
	DATABASE_URL=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	deploy/cloud-sql/run-migrations.sh && \
	cd orchestration && \
	ORCH_LIVE_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_LIVE_STORY_URL=http://127.0.0.1:$(STORY_PORT)/mcp \
	ORCH_LIVE_ARTIFACT_URL=http://127.0.0.1:$(ARTIFACT_PORT)/mcp \
	ORCH_LIVE_REPORT_URL=http://127.0.0.1:$(REPORT_PORT)/mcp \
	ORCH_LIVE_BUSINESS_URL=http://127.0.0.1:$(BUSINESS_PORT) \
	ORCH_LIVE_ENGINEERING_URL=http://127.0.0.1:$(ENGINEERING_PORT) \
	ORCH_LIVE_SYNTHESIS_URL=http://127.0.0.1:$(SYNTHESIS_PORT) \
	ORCH_LIVE_FACILITATOR_URL=http://127.0.0.1:$(FACILITATOR_PORT) \
	ORCH_LIVE_BUCKET=$${ARTIFACT_BUCKET:-artifacts-local} \
	ORCH_TEST_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_STORY_URL=http://story:8080/mcp ORCH_ARTIFACT_URL=http://artifact:8080/mcp \
	ORCH_REPORT_URL=http://report:8080/mcp ORCH_BUCKET=artifacts-local \
	ORCH_BUSINESS_URL=http://business:8080 ORCH_ENGINEERING_URL=http://engineering:8080 \
	ORCH_SYNTHESIS_URL=http://synthesis:8080 ORCH_FACILITATOR_URL=http://facilitator:8080 \
	uv run --no-project --with-requirements requirements.lock \
		--with-requirements tests/requirements.lock \
		--with-editable . --with-editable ../shared/review_schemas \
		python -m pytest tests/test_flow1_live.py -q -rs

orchestration-turns-live-test: ## Phase 6 increment 3 live gate: one real dialogue turn over compose (main PC; needs agents-compose-up)
	container=$$(docker run -d --rm -e POSTGRES_USER=orch \
		-e POSTGRES_PASSWORD=orch -e POSTGRES_DB=orchestration \
		-p 127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}:5432 postgres:16); \
	trap 'docker rm -f $$container >/dev/null 2>&1' EXIT; \
	for i in $$(seq 1 60); do \
		docker exec $$container pg_isready -U orch >/dev/null 2>&1 && break; sleep 0.5; \
	done; \
	docker exec $$container pg_isready -U orch >/dev/null 2>&1 || { echo "test Postgres not ready" >&2; exit 1; }; \
	DATABASE_URL=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	deploy/cloud-sql/run-migrations.sh && \
	cd orchestration && \
	ORCH_LIVE_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_LIVE_STORY_URL=http://127.0.0.1:$(STORY_PORT)/mcp \
	ORCH_LIVE_ARTIFACT_URL=http://127.0.0.1:$(ARTIFACT_PORT)/mcp \
	ORCH_LIVE_REPORT_URL=http://127.0.0.1:$(REPORT_PORT)/mcp \
	ORCH_LIVE_BUSINESS_URL=http://127.0.0.1:$(BUSINESS_PORT) \
	ORCH_LIVE_ENGINEERING_URL=http://127.0.0.1:$(ENGINEERING_PORT) \
	ORCH_LIVE_SYNTHESIS_URL=http://127.0.0.1:$(SYNTHESIS_PORT) \
	ORCH_LIVE_FACILITATOR_URL=http://127.0.0.1:$(FACILITATOR_PORT) \
	ORCH_LIVE_BUCKET=$${ARTIFACT_BUCKET:-artifacts-local} \
	ORCH_TEST_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_STORY_URL=http://story:8080/mcp ORCH_ARTIFACT_URL=http://artifact:8080/mcp \
	ORCH_REPORT_URL=http://report:8080/mcp ORCH_BUCKET=artifacts-local \
	ORCH_BUSINESS_URL=http://business:8080 ORCH_ENGINEERING_URL=http://engineering:8080 \
	ORCH_SYNTHESIS_URL=http://synthesis:8080 ORCH_FACILITATOR_URL=http://facilitator:8080 \
	uv run --no-project --with-requirements requirements.lock \
		--with-requirements tests/requirements.lock \
		--with-editable . --with-editable ../shared/review_schemas \
		python -m pytest tests/test_turns_live.py -q -rs

orchestration-finalize-live-test: ## Phase 6 increment 4 live gate: full session to downloaded report (main PC; needs agents-compose-up)
	container=$$(docker run -d --rm -e POSTGRES_USER=orch \
		-e POSTGRES_PASSWORD=orch -e POSTGRES_DB=orchestration \
		-p 127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}:5432 postgres:16); \
	trap 'docker rm -f $$container >/dev/null 2>&1' EXIT; \
	for i in $$(seq 1 60); do \
		docker exec $$container pg_isready -U orch >/dev/null 2>&1 && break; sleep 0.5; \
	done; \
	docker exec $$container pg_isready -U orch >/dev/null 2>&1 || { echo "test Postgres not ready" >&2; exit 1; }; \
	DATABASE_URL=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	deploy/cloud-sql/run-migrations.sh && \
	cd orchestration && \
	ORCH_LIVE_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_LIVE_STORY_URL=http://127.0.0.1:$(STORY_PORT)/mcp \
	ORCH_LIVE_ARTIFACT_URL=http://127.0.0.1:$(ARTIFACT_PORT)/mcp \
	ORCH_LIVE_REPORT_URL=http://127.0.0.1:$(REPORT_PORT)/mcp \
	ORCH_LIVE_BUSINESS_URL=http://127.0.0.1:$(BUSINESS_PORT) \
	ORCH_LIVE_ENGINEERING_URL=http://127.0.0.1:$(ENGINEERING_PORT) \
	ORCH_LIVE_SYNTHESIS_URL=http://127.0.0.1:$(SYNTHESIS_PORT) \
	ORCH_LIVE_FACILITATOR_URL=http://127.0.0.1:$(FACILITATOR_PORT) \
	ORCH_LIVE_BUCKET=$${ARTIFACT_BUCKET:-artifacts-local} \
	ORCH_LIVE_GCS_PUBLIC_URL=https://127.0.0.1:$${FAKE_GCS_HTTPS_PORT:-9026} \
	ORCH_TEST_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_STORY_URL=http://story:8080/mcp ORCH_ARTIFACT_URL=http://artifact:8080/mcp \
	ORCH_REPORT_URL=http://report:8080/mcp ORCH_BUCKET=artifacts-local \
	ORCH_BUSINESS_URL=http://business:8080 ORCH_ENGINEERING_URL=http://engineering:8080 \
	ORCH_SYNTHESIS_URL=http://synthesis:8080 ORCH_FACILITATOR_URL=http://facilitator:8080 \
	uv run --no-project --with-requirements requirements.lock \
		--with-requirements tests/requirements.lock \
		--with-editable . --with-editable ../shared/review_schemas \
		python -m pytest tests/test_finalize_live.py -q -rs

orchestration-integration-test: ## Phase 6 increment 5 exit gate: live integration suite over compose (main PC; needs agents-compose-up)
	container=$$(docker run -d --rm -e POSTGRES_USER=orch \
		-e POSTGRES_PASSWORD=orch -e POSTGRES_DB=orchestration \
		-p 127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}:5432 postgres:16); \
	trap 'docker rm -f $$container >/dev/null 2>&1' EXIT; \
	for i in $$(seq 1 60); do \
		docker exec $$container pg_isready -U orch >/dev/null 2>&1 && break; sleep 0.5; \
	done; \
	docker exec $$container pg_isready -U orch >/dev/null 2>&1 || { echo "test Postgres not ready" >&2; exit 1; }; \
	DATABASE_URL=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	deploy/cloud-sql/run-migrations.sh && \
	cd orchestration && \
	ORCH_LIVE_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_LIVE_STORY_URL=http://127.0.0.1:$(STORY_PORT)/mcp \
	ORCH_LIVE_ARTIFACT_URL=http://127.0.0.1:$(ARTIFACT_PORT)/mcp \
	ORCH_LIVE_REPORT_URL=http://127.0.0.1:$(REPORT_PORT)/mcp \
	ORCH_LIVE_BUSINESS_URL=http://127.0.0.1:$(BUSINESS_PORT) \
	ORCH_LIVE_ENGINEERING_URL=http://127.0.0.1:$(ENGINEERING_PORT) \
	ORCH_LIVE_SYNTHESIS_URL=http://127.0.0.1:$(SYNTHESIS_PORT) \
	ORCH_LIVE_FACILITATOR_URL=http://127.0.0.1:$(FACILITATOR_PORT) \
	ORCH_LIVE_BUCKET=$${ARTIFACT_BUCKET:-artifacts-local} \
	ORCH_LIVE_GCS_PUBLIC_URL=https://127.0.0.1:$${FAKE_GCS_HTTPS_PORT:-9026} \
	ORCH_TEST_DB_DSN=postgres://orch:orch@127.0.0.1:$${ORCH_TEST_DB_PORT:-9030}/orchestration \
	ORCH_STORY_URL=http://story:8080/mcp ORCH_ARTIFACT_URL=http://artifact:8080/mcp \
	ORCH_REPORT_URL=http://report:8080/mcp ORCH_BUCKET=artifacts-local \
	ORCH_BUSINESS_URL=http://business:8080 ORCH_ENGINEERING_URL=http://engineering:8080 \
	ORCH_SYNTHESIS_URL=http://synthesis:8080 ORCH_FACILITATOR_URL=http://facilitator:8080 \
	uv run --no-project --with-requirements requirements.lock \
		--with-requirements tests/requirements.lock \
		--with-editable . --with-editable ../shared/review_schemas \
		python -m pytest tests/integration -q -rs

webui-test: ## Phase 7: webui deterministic tests (uv package + vitest frontend)
	cd webui && \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable . python -m pytest tests -q && \
	npm ci --silent && npm test

compose-up: ## Local development stack (Phase 4 `local` profile)
	[ -f deploy/env/.env ] || cp deploy/env/.env.example deploy/env/.env
	cd deploy && docker compose --profile local --env-file env/.env up -d --build

compose-down: ## Stop the local development stack (Phase 4)
	cd deploy && docker compose --profile local --env-file env/.env down

compose-contract-test: ## Phase 4 cross-service contract tests over HTTP (needs compose-up)
	for i in $$(seq 1 60); do \
		ok=1; for port in $(STORY_PORT) $(ARTIFACT_PORT) $(REPORT_PORT); do \
			curl -sf http://127.0.0.1:$$port/health >/dev/null || ok=0; \
		done; [ $$ok = 1 ] && break; sleep 1; \
	done; \
	cd tests/contract && \
	uv run --no-project --with-requirements requirements.lock \
		python -m pytest . -q

evaluation-unit-test: ## Phase 9: evaluation package unit tests (no stack, no model calls)
	cd tests/evaluation && \
	uv run --no-project --with-requirements requirements.lock \
		python -m pytest tests -q

evaluation-test: ## Phase 9: evaluation suite over compose (needs agents-compose-up; TEMPLATES=t1 default; JUDGE=1 adds judged stage)
	cd tests/evaluation && \
	GOOGLE_CLOUD_PROJECT=$${GOOGLE_CLOUD_PROJECT:-$$PROJECT_ID} \
	GOOGLE_CLOUD_LOCATION=$${GOOGLE_CLOUD_LOCATION:-$${REGION:-europe-west4}} \
	uv run --no-project --with-requirements requirements.lock \
		python -m evaluation.runner --base-url $${EVAL_BASE_URL:-http://127.0.0.1:8130} \
		--templates $${TEMPLATES:-t1} $${JUDGE:+--judge} \
		--orchestration-dsn postgresql://facilitator:facilitator@127.0.0.1:$${POSTGRES_HOST_PORT:-15432}/orchestration \
		--facilitator-dsn postgresql://facilitator:facilitator@127.0.0.1:$${POSTGRES_HOST_PORT:-15432}/facilitator

evaluation-smoke: ## Phase 9: smoke set — t1 deterministic suite + ONE judged clean case (spends tokens)
	cd tests/evaluation && \
	GOOGLE_CLOUD_PROJECT=$${GOOGLE_CLOUD_PROJECT:-$$PROJECT_ID} \
	GOOGLE_CLOUD_LOCATION=$${GOOGLE_CLOUD_LOCATION:-$${REGION:-europe-west4}} \
	uv run --no-project --with-requirements requirements.lock \
		python -m evaluation.runner --smoke --label smoke \
		--orchestration-dsn postgresql://facilitator:facilitator@127.0.0.1:$${POSTGRES_HOST_PORT:-15432}/orchestration \
		--facilitator-dsn postgresql://facilitator:facilitator@127.0.0.1:$${POSTGRES_HOST_PORT:-15432}/facilitator

# Phase 4 increment 5: Cloud Run deploys + smoke.
# _mcp_url is a shell command (run via $(...) in recipes) reading the
# terraform outputs (tier-1 read); the ID token impersonates sa-orchestration.
define _mcp_url
terraform -chdir=infra output -json mcp_services | jq -r ".$(1).url // empty"
endef

mcp-story-deploy: ## Phase 4: build+push story MCP image (prints terraform -var line)
	deploy/cloud-run/story/deploy.sh

mcp-artifact-deploy: ## Phase 4: build+push artifact MCP image (prints terraform -var line)
	deploy/cloud-run/artifact/deploy.sh

mcp-report-deploy: ## Phase 4: build+push report MCP image (prints terraform -var line)
	deploy/cloud-run/report/deploy.sh

mcp-story-smoke: ## Phase 4: smoke story MCP on Cloud Run (impersonated sa-orchestration)
	$(guard-project)
	source infra/envs/home.env && url="$$( $(call _mcp_url,story))" && \
	[ -n "$$url" ] || { echo "story service not deployed (terraform output null)"; exit 2; } && \
	MCP_ID_TOKEN="$$(gcloud auth print-identity-token \
		--impersonate-service-account=sa-orchestration@$${PROJECT_ID}.iam.gserviceaccount.com \
		--audiences="$$url" --include-email)" \
	uv run --no-project --with-requirements deploy/cloud-run/smoke/requirements.lock \
		python deploy/cloud-run/smoke/smoke.py story "$$url"

mcp-artifact-smoke: ## Phase 4: smoke artifact MCP on Cloud Run
	$(guard-project)
	source infra/envs/home.env && url="$$( $(call _mcp_url,artifact))" && \
	[ -n "$$url" ] || { echo "artifact service not deployed (terraform output null)"; exit 2; } && \
	MCP_ID_TOKEN="$$(gcloud auth print-identity-token \
		--impersonate-service-account=sa-orchestration@$${PROJECT_ID}.iam.gserviceaccount.com \
		--audiences="$$url" --include-email)" \
	uv run --no-project --with-requirements deploy/cloud-run/smoke/requirements.lock \
		python deploy/cloud-run/smoke/smoke.py artifact "$$url"

mcp-report-smoke: ## Phase 4: smoke report MCP (renders from a live artifact)
	$(guard-project)
	source infra/envs/home.env && url="$$( $(call _mcp_url,report))" && \
	art_url="$$( $(call _mcp_url,artifact))" && \
	[ -n "$$url" ] && [ -n "$$art_url" ] || { echo "report/artifact service not deployed (terraform output null)"; exit 2; } && \
	MCP_ARTIFACT_URL="$$art_url" \
	MCP_ID_TOKEN="$$(gcloud auth print-identity-token \
		--impersonate-service-account=sa-orchestration@$${PROJECT_ID}.iam.gserviceaccount.com \
		--audiences="$$url" --include-email)" \
	MCP_ID_TOKEN_ARTIFACT="$$(gcloud auth print-identity-token \
		--impersonate-service-account=sa-orchestration@$${PROJECT_ID}.iam.gserviceaccount.com \
		--audiences="$$art_url" --include-email)" \
	uv run --no-project --with-requirements deploy/cloud-run/smoke/requirements.lock \
		python deploy/cloud-run/smoke/smoke.py report "$$url" "$$art_url"

terraform-plan: ## Review plan for the home environment
	terraform -chdir=infra plan -var-file=envs/home.tfvars -out=home.tfplan

terraform-apply: ## Apply the saved home plan (write action)
	terraform -chdir=infra apply home.tfplan

artifacts-purge: ## DESTRUCTIVE: delete all runs/ artifacts (dev hygiene; owner-run)
	$(guard-project)
	@echo "This deletes EVERYTHING under gs://$(PROJECT_ID)-artifacts/runs/ (smoke/test/demo artifacts)."
	@echo "Dev artifacts are disposable; the dataset is re-pushable via make dataset-push."
	@printf "Type 'purge' to confirm: " && read ans && [ "$$ans" = purge ] || { echo "aborted"; exit 1; }
	gcloud storage rm --recursive "gs://$(PROJECT_ID)-artifacts/runs/" && echo "artifacts purged"

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

agents-deploy-facilitator agents-deploy-business-reviewer agents-deploy-engineering-reviewer agents-deploy-synthesis: ## Phase 8 inc 3: deploy one agent to Agent Engine (tier-2, new versioned resource)
	$(guard-project)
	deploy/agents/$(patsubst agents-deploy-%,%,$@)/deploy.sh

facilitator-adapter-test: ## Phase 5: facilitator adapter deterministic tests (no LLM)
	cd deploy/compose/adapters/facilitator && \
	PROMPTS_DIR=$$PWD/../../../../prompts \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable ../../../../shared/agent_kit \
		--with-editable ../../../../shared/review_schemas \
		--with-editable ../../../../agents/facilitator \
		--with-editable . python -m pytest tests -q

facilitator-live-test: ## Phase 5 exit gate: example-interaction walkthrough over compose HTTP (main PC; needs agents-compose-up)
	source infra/envs/home.env && \
	cd deploy/compose/adapters/facilitator && \
	PROMPTS_DIR=$$PWD/../../../../prompts \
	AGENT_LIVE_TESTS=1 \
	BUSINESS_REVIEWER_URL=http://127.0.0.1:$${BUSINESS_REVIEWER_PORT:-8111} \
	ENGINEERING_REVIEWER_URL=http://127.0.0.1:$${ENGINEERING_REVIEWER_PORT:-8112} \
	SYNTHESIS_URL=http://127.0.0.1:$${SYNTHESIS_PORT:-8113} \
	FACILITATOR_URL=http://127.0.0.1:$${FACILITATOR_PORT:-8114} \
	uv run --no-project --with-requirements tests/requirements.lock \
		--with-editable ../../../../shared/agent_kit \
		--with-editable ../../../../shared/review_schemas \
		--with-editable ../../../../agents/facilitator \
		--with-editable . python -m pytest tests/test_live_walkthrough.py -q

agents-compose-up: ## Local stack incl. the four agent adapters (`local` + `local-agents` profiles)
	[ -f deploy/env/.env ] || cp deploy/env/.env.example deploy/env/.env
	@grep -q '^GOOGLE_CLOUD_PROJECT=..*' deploy/env/.env || { \
		echo "ERROR: set GOOGLE_CLOUD_PROJECT in deploy/env/.env (adapter containers need the Vertex project)" >&2; exit 2; }
	@[ -f $$HOME/.config/gcloud/application_default_credentials.json ] || { \
		echo "ERROR: ADC file not found at \$$HOME/.config/gcloud (adapter containers mount it read-only)" >&2; exit 2; }
	cd deploy && HOST_UID=$$(id -u) HOST_GID=$$(id -g) docker compose --profile local --profile local-agents --env-file env/.env up -d --build

agents-compose-down: ## Stop the local stack incl. agent adapters
	cd deploy && docker compose --profile local --profile local-agents --env-file env/.env down
