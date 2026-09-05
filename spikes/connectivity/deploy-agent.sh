#!/usr/bin/env bash
# Stage and deploy the disposable connectivity Agent Engine caller.
#
# Tier-2 (write) action: creates one Agent Engine resource, billed on demand.
# It attaches sa-facilitator and injects the Cloud Run URL as both the agent
# environment value and ID-token audience. The staging directory and deploy log
# are retained and printed for troubleshooting; they contain no secrets.
#
# ADK 2.8.0 gotchas (learned live, 2026-09-05):
# - Passing --agent_engine_id makes the CLI skip create() and update() a
#   nonexistent reasoningEngine -> bare 400 INVALID_ARGUMENT. We deploy without
#   an ID (the platform generates a numeric one) and parse
#   "Created a new instance:" from the output.
# - The CLI exits 0 even after printing "Deploy failed", so the script checks
#   the log itself.
set -euo pipefail

cd "$(dirname "$0")"
source ../../infra/envs/home.env
: "${PROJECT_ID:?PROJECT_ID not set in infra/envs/home.env}"
REGION="${REGION:-europe-west4}"
SERVICE_URL="$(terraform -chdir=../../infra output -json connectivity_spike | jq -r .service_url)"
FACILITATOR_SA="$(terraform -chdir=../../infra output -json service_accounts | jq -r '.runtime."sa-facilitator"')"
: "${SERVICE_URL:?connectivity spike service_url is not set}"
[[ "$FACILITATOR_SA" == sa-facilitator@*.iam.gserviceaccount.com ]] || {
  echo "unexpected facilitator SA: '$FACILITATOR_SA'" >&2
  exit 1
}

STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/spike-agent.XXXXXX")"
cp -R spike_agent "$STAGE_DIR/"
rm -rf "$STAGE_DIR/spike_agent/__pycache__"
cp spike_agent/requirements.lock "$STAGE_DIR/spike_agent/requirements.txt"
cat >"$STAGE_DIR/spike_agent/.agent_engine_config.json" <<EOF
{
  "service_account": "$FACILITATOR_SA",
  "env_vars": {
    "SPIKE_SERVICE_URL": "$SERVICE_URL"
  }
}
EOF

export SPIKE_SERVICE_URL="$SERVICE_URL"
DEPLOY_LOG="$(mktemp "${TMPDIR:-/tmp}/spike-agent-deploy.XXXXXX.log")"
printf 'staging directory: %s\ndeploy log: %s\nservice URL/audience: %s\nruntime service account: %s\n' \
  "$STAGE_DIR" "$DEPLOY_LOG" "$SERVICE_URL" "$FACILITATOR_SA"

uv run --with-requirements spike_agent/requirements.lock adk deploy agent_engine \
  --project="$PROJECT_ID" --region="$REGION" \
  "$STAGE_DIR/spike_agent" 2>&1 | tee "$DEPLOY_LOG"

if grep -q "Deploy failed" "$DEPLOY_LOG"; then
  echo "deployment failed (see log above and $DEPLOY_LOG)" >&2
  exit 1
fi
RESOURCE_NAME="$(grep -oP 'Created a new instance: \Kprojects/[^ ]+' "$DEPLOY_LOG" | head -1)"
: "${RESOURCE_NAME:?could not parse created reasoningEngine name from deploy log}"
AGENT_ENGINE_ID="${RESOURCE_NAME##*/}"

printf '\ndeployed agent engine id: %s\nresource name: %s\nnext: ./run-agent-trace.sh %s\n' \
  "$AGENT_ENGINE_ID" "$RESOURCE_NAME" "$AGENT_ENGINE_ID"
