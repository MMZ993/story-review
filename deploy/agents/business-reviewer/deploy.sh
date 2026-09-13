#!/usr/bin/env bash
# Deploy the business-reviewer agent to Agent Engine (Phase 8 increment 3).
#
# Tier-2 (write): creates a NEW billable Agent Engine resource
# <slug>-<short-sha> (D5/D24-5: retained until the versioning proof).
# Source infra/envs/home.env first. Stages from the repository root per
# docs/operations/deployment.md; prints the created resource name for the
# runbook and the orchestration AGENT_BUSINESS_REVIEWER_RESOURCE pointer.
set -euo pipefail

cd "$(dirname "$0")/../../.."
source infra/envs/home.env
: "${PROJECT_ID:?PROJECT_ID not set}" ; REGION="${REGION:-europe-west4}"

source deploy/agents/common.sh

stage="$(mktemp -d /tmp/agent-business-reviewer-XXXXXX)"
out="$(agents_stage business-reviewer business_reviewer "$stage")"
agent_dir="$(echo "$out" | cut -d' ' -f2)"
extras="$(echo "$out" | cut -d' ' -f3-)"

agents_env business-reviewer > "$agent_dir/.env"
agents_config business-reviewer "sa-business-reviewer@${PROJECT_ID}.iam.gserviceaccount.com" > "$agent_dir/.agent_engine_config.json"

agents_deploy business-reviewer "$stage" "$agent_dir" $extras
echo "staging kept for inspection: $stage"
