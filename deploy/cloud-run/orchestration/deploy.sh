#!/usr/bin/env bash
# Build and deploy the orchestration service to Cloud Run (Phase 8
# increment 4).
#
# Tier-2 (write) action: pushes an image to the existing Artifact Registry
# repository and updates/creates the `orchestration` Cloud Run service.
# Source infra/envs/home.env first, and fill deploy/cloud-run/orchestration/.env
# from .env.example with the current Agent Engine release pointers (Runbook 14).
#
# Shape (docs/operations/deployment.md + plan §increment 4):
# - AE invocation mode (ORCH_AGENT_MODE=ae) — the service calls the four
#   deployed agents over :streamQuery?alt=sse as sa-orchestration
#   (roles/aiplatform.user);
# - record pool on Cloud SQL IAM auth (cloudsql-iam:/// DSN + connector,
#   no passwords) with the instance attached as a Cloud SQL volume;
# - artifacts bucket + MCP service URLs from terraform outputs;
# - request timeout above the 300 s agent-work deadline;
# - not publicly reachable: ingress control is incremental 5's concern.
set -euo pipefail

cd "$(dirname "$0")/../../.."
source infra/envs/home.env
ENV_DIR="deploy/cloud-run/orchestration"
[ -f "$ENV_DIR/.env" ] && source "$ENV_DIR/.env"
: "${PROJECT_ID:?PROJECT_ID not set in infra/envs/home.env}"
REGION="${REGION:-europe-west4}"
REPO="$REGION-docker.pkg.dev/$PROJECT_ID/service-images"
TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M)-$(git rev-parse --short HEAD)}"
IMAGE="$REPO/orchestration:$TAG"

# The tag maps images to commits (same convention as deploy/agents);
# deploying uncommitted code breaks that map — commit first, or opt in
# explicitly with ALLOW_DIRTY_DEPLOY=1.
if ! git diff --quiet || ! git diff --cached --quiet; then
    if [ "${ALLOW_DIRTY_DEPLOY:-}" = "1" ]; then
        echo "WARNING: dirty tree deploy (ALLOW_DIRTY_DEPLOY=1): tag $TAG" >&2
    else
        echo "refusing to deploy: working tree has uncommitted changes" >&2
        echo "commit first, or set ALLOW_DIRTY_DEPLOY=1" >&2
        exit 2
    fi
fi

: "${ORCH_AE_BUSINESS_RESOURCE:?ORCH_AE_BUSINESS_RESOURCE not set (see .env.example)}"
: "${ORCH_AE_ENGINEERING_RESOURCE:?ORCH_AE_ENGINEERING_RESOURCE not set (see .env.example)}"
: "${ORCH_AE_SYNTHESIS_RESOURCE:?ORCH_AE_SYNTHESIS_RESOURCE not set (see .env.example)}"
: "${ORCH_AE_FACILITATOR_RESOURCE:?ORCH_AE_FACILITATOR_RESOURCE not set (see .env.example)}"
: "${ORCH_AE_BUSINESS_VERSION:?ORCH_AE_BUSINESS_VERSION not set (see .env.example)}"
: "${ORCH_AE_ENGINEERING_VERSION:?ORCH_AE_ENGINEERING_VERSION not set (see .env.example)}"
: "${ORCH_AE_SYNTHESIS_VERSION:?ORCH_AE_SYNTHESIS_VERSION not set (see .env.example)}"
: "${ORCH_AE_FACILITATOR_VERSION:?ORCH_AE_FACILITATOR_VERSION not set (see .env.example)}"

STORY_URL="$(terraform -chdir=infra output -json mcp_services | jq -r .story.url)/mcp"
ARTIFACT_URL="$(terraform -chdir=infra output -json mcp_services | jq -r .artifact.url)/mcp"
REPORT_URL="$(terraform -chdir=infra output -json mcp_services | jq -r .report.url)/mcp"
BUCKET="$(terraform -chdir=infra output -json artifact_bucket_name | jq -r .)"
INSTANCE_CONN="$(terraform -chdir=infra output -json cloud_sql | jq -r .instance_connection_name)"

echo "building $IMAGE (context: repository root)"
docker build -t "$IMAGE" -f orchestration/Dockerfile .
docker push "$IMAGE"

echo "deploying Cloud Run service orchestration ($TAG)"
gcloud run deploy orchestration \
    --project "$PROJECT_ID" --region "$REGION" \
    --image "$IMAGE" \
    --service-account "sa-orchestration@${PROJECT_ID}.iam.gserviceaccount.com" \
    --add-cloudsql-instances "$INSTANCE_CONN" \
    --timeout 600 \
    --cpu 1 --memory 512Mi --min-instances 0 --max-instances 2 \
    --no-allow-unauthenticated \
    --set-env-vars \
"ORCH_AGENT_MODE=ae,\
ORCH_MCP_ID_TOKEN_AUTH=1,\
ORCH_DB_DSN=cloudsql-iam:///${INSTANCE_CONN}/orchestration,\
ORCH_STORY_URL=${STORY_URL},\
ORCH_ARTIFACT_URL=${ARTIFACT_URL},\
ORCH_REPORT_URL=${REPORT_URL},\
ORCH_BUCKET=${BUCKET},\
ORCH_AE_BUSINESS_RESOURCE=${ORCH_AE_BUSINESS_RESOURCE},\
ORCH_AE_BUSINESS_VERSION=${ORCH_AE_BUSINESS_VERSION},\
ORCH_AE_ENGINEERING_RESOURCE=${ORCH_AE_ENGINEERING_RESOURCE},\
ORCH_AE_ENGINEERING_VERSION=${ORCH_AE_ENGINEERING_VERSION},\
ORCH_AE_SYNTHESIS_RESOURCE=${ORCH_AE_SYNTHESIS_RESOURCE},\
ORCH_AE_SYNTHESIS_VERSION=${ORCH_AE_SYNTHESIS_VERSION},\
ORCH_AE_FACILITATOR_RESOURCE=${ORCH_AE_FACILITATOR_RESOURCE},\
ORCH_AE_FACILITATOR_VERSION=${ORCH_AE_FACILITATOR_VERSION}"

URL="$(gcloud run services describe orchestration \
    --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)')"
cat <<EOM

deployed: $URL (image $TAG)

health check (read-only, authenticated):
  curl -H "Authorization: Bearer \$(gcloud auth print-identity-token)" \\
    "$URL/health"
EOM
