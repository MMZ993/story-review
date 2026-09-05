#!/usr/bin/env bash
# Build and push the connectivity-spike MCP image (Phase 1, increment 3).
#
# Tier-2 (write) action: pushes an image to the existing Artifact Registry
# repository. Source infra/envs/home.env first. Terraform (separate reviewed
# plan/apply) consumes the printed image reference via -var spike_mcp_image=...
#
# Usage: ./deploy-mcp.sh [tag]   (default tag: yyyyMMdd-HHMM-<short sha>)
set -euo pipefail

cd "$(dirname "$0")"

source ../../infra/envs/home.env
: "${PROJECT_ID:?PROJECT_ID not set in infra/envs/home.env}"
REGION="${REGION:-europe-west4}"
REPO="$REGION-docker.pkg.dev/$PROJECT_ID/service-images"
IMAGE_BASE="$REPO/spike-connectivity-mcp"
TAG="${1:-$(date +%Y%m%d-%H%M)-$(git rev-parse --short HEAD)}"
IMAGE="$IMAGE_BASE:$TAG"

echo "building $IMAGE"
docker build -t "$IMAGE" -f Dockerfile .
docker push "$IMAGE"

cat <<EOF
image pushed: $IMAGE

next (reviewed, tier-2):
  cd ../../infra
  terraform plan -var-file=envs/home.tfvars \\
    -var 'spike_mcp_image=$IMAGE' -out=home-spike-mcp.tfplan
EOF
