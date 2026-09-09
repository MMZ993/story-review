#!/usr/bin/env bash
# Build and push the artifact MCP service image (Phase 4 increment 5).
#
# Tier-2 (write) action: pushes an image to the existing Artifact Registry
# repository. Source infra/envs/home.env first. Terraform (separate reviewed
# plan/apply) consumes the printed image reference via -var mcp_artifact_image=...
#
# Usage: ./deploy.sh [tag]   (default tag: yyyyMMdd-HHMM-<short sha>)
set -euo pipefail

cd "$(dirname "$0")"

source ../../../infra/envs/home.env
# optional local overrides (deploy/cloud-run/artifact/.env, gitignored)
[ -f .env ] && source .env
: "${PROJECT_ID:?PROJECT_ID not set in infra/envs/home.env}"
REGION="${REGION:-europe-west4}"
REPO="$REGION-docker.pkg.dev/$PROJECT_ID/service-images"
IMAGE_BASE="$REPO/mcp-artifact"
TAG="${IMAGE_TAG:-${1:-$(date +%Y%m%d-%H%M)-$(git rev-parse --short HEAD)}}"
IMAGE="$IMAGE_BASE:$TAG"

echo "building $IMAGE"
docker build -t "$IMAGE" -f ../../../mcp_servers/artifact/Dockerfile ../../../
docker push "$IMAGE"

cat <<EOM
image pushed: $IMAGE

next (reviewed, tier-2):
  cd ../../../infra
  terraform plan -var-file=envs/home.tfvars \
    -var 'mcp_artifact_image=$IMAGE' -out=home.tfplan
EOM
