#!/usr/bin/env bash
# Build and deploy the webui service to Cloud Run (Phase 8 increment 5).
#
# Tier-2 (write) action: pushes an image to the existing Artifact Registry
# repository and updates/creates the `webui` Cloud Run service, plus an
# idempotent roles/run.invoker IAM binding for sa-webui on the orchestration
# service. Source infra/envs/home.env first.
#
# Shape (D24-2 + docs/operations/deployment.md):
# - the ONLY public surface: unauthenticated ingress (anonymous multi-user
#   scoping via the browser-minted X-User-Id cookie, D24-3);
# - orchestration is reached through the same-origin /api proxy with an
#   audience-scoped ID token (ORCHESTRATION_ID_TOKEN_AUTH=1) — orchestration
#   itself stays IAM-gated (no public ingress);
# - sa-webui (terraform-managed) runs the service.
#
# Known deviation (recorded in Runbook 14 inc 5): the run.invoker binding on
# orchestration lives here, not in terraform, because the orchestration
# Cloud Run service was deployed via gcloud (increment 4) and is not a
# terraform resource; the binding is idempotent (policyDiff suppresses
# no-op adds).
set -euo pipefail

cd "$(dirname "$0")/../../.."
source infra/envs/home.env
: "${PROJECT_ID:?PROJECT_ID not set in infra/envs/home.env}"
REGION="${REGION:-europe-west4}"
REPO="$REGION-docker.pkg.dev/$PROJECT_ID/service-images"
TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M)-$(git rev-parse --short HEAD)}"
IMAGE="$REPO/webui:$TAG"

# The tag maps images to commits (same convention as deploy/agents +
# orchestration); deploying uncommitted code breaks that map — commit first,
# or opt in explicitly with ALLOW_DIRTY_DEPLOY=1. Checks untracked files
# too (`git diff --quiet` alone would miss a brand-new module).
if [ -n "$(git status --porcelain)" ]; then
    if [ "${ALLOW_DIRTY_DEPLOY:-}" = "1" ]; then
        echo "WARNING: dirty tree deploy (ALLOW_DIRTY_DEPLOY=1): tag $TAG" >&2
    else
        echo "refusing to deploy: working tree has uncommitted changes" >&2
        echo "commit first, or set ALLOW_DIRTY_DEPLOY=1" >&2
        exit 2
    fi
fi

# gcloud run surface flags: --project/--region apply to every call below.
GC() { gcloud run --project "$PROJECT_ID" --region "$REGION" "$@"; }

ORCH_URL="$($GC services describe orchestration --format 'value(status.url)')"
SA_WEBUI="sa-webui@${PROJECT_ID}.iam.gserviceaccount.com"

echo "building $IMAGE (context: repository root)"
docker build -t "$IMAGE" -f webui/Dockerfile .
docker push "$IMAGE"

echo "granting sa-webui run.invoker on orchestration (idempotent)"
$GC services add-iam-policy-binding orchestration \
    --member "serviceAccount:$SA_WEBUI" \
    --role roles/run.invoker \
    --quiet >/dev/null

echo "deploying Cloud Run service webui ($TAG)"
$GC deploy webui \
    --image "$IMAGE" \
    --service-account "$SA_WEBUI" \
    --timeout 600 \
    --cpu 1 --memory 256Mi --min-instances 0 --max-instances 2 \
    --allow-unauthenticated \
    --set-env-vars \
"ORCHESTRATION_BASE_URL=${ORCH_URL},\
ORCHESTRATION_ID_TOKEN_AUTH=1"

URL="$($GC services describe webui --format 'value(status.url)')"
cat <<EOM

deployed: $URL (image $TAG)

reachability check (read-only, public):
  curl "$URL/health"

next: route the Cloudflare subdomain (e.g. story-review.mmz.sh) to this
URL — custom-domain mapping vs proxied CNAME settled empirically per the
increment-5 plan, then browser walkthrough over the public domain.
EOM
