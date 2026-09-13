#!/usr/bin/env bash
# Deploy the facilitator agent to Agent Engine (Phase 8 increment 3).
#
# Tier-2 (write): creates a NEW billable Agent Engine resource
# facilitator-<short-sha> (D5/D24-5: retained until the versioning proof).
# Source infra/envs/home.env first. Session state runs on Cloud SQL
# PostgreSQL (facilitator database, IAM login as sa-facilitator — D24
# amendment 1); the story/artifact toolsets authenticate with
# audience-scoped ID tokens of the same attached service account.
set -euo pipefail

cd "$(dirname "$0")/../../.."
source infra/envs/home.env
: "${PROJECT_ID:?PROJECT_ID not set}" ; REGION="${REGION:-europe-west4}"

source deploy/agents/common.sh

STORY_URL="$(terraform -chdir=infra output -json mcp_services | jq -r .story.url)"
ARTIFACT_URL="$(terraform -chdir=infra output -json mcp_services | jq -r .artifact.url)"
INSTANCE_CONN="$(terraform -chdir=infra output -json cloud_sql | jq -r .instance_connection_name)"

stage="$(mktemp -d /tmp/agent-facilitator-XXXXXX)"
out="$(agents_stage facilitator facilitator "$stage")"
agent_dir="$(echo "$out" | cut -d' ' -f2)"
extras="$(echo "$out" | cut -d' ' -f3-)"

{ agents_env facilitator
  echo "FACILITATOR_STORY_URL=$STORY_URL/mcp"
  echo "FACILITATOR_ARTIFACT_URL=$ARTIFACT_URL/mcp"
} > "$agent_dir/.env"
agents_config facilitator "sa-facilitator@${PROJECT_ID}.iam.gserviceaccount.com" > "$agent_dir/.agent_engine_config.json"

AE_SESSION_SERVICE_URI="cloudsql-iam:///$INSTANCE_CONN/facilitator" \
    agents_deploy facilitator "$stage" "$agent_dir" $extras
echo "staging kept for inspection: $stage"
