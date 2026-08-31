#!/usr/bin/env bash
#
# Build the image for ARM64, push it to ECR, and roll the service onto it.
#
# The service always points at :latest, so shipping code is a push plus a
# forced deployment -- Terraform is not involved and does not need to run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../terraform"

REGION="$(terraform output -raw region 2>/dev/null || echo "${AWS_REGION:-us-east-2}")"
REPO="$(terraform output -raw ecr_repository_url)"
CLUSTER="$(terraform output -raw cluster_name)"
SERVICE="$(terraform output -raw service_name)"
ROOT="$(cd ../.. && pwd)"

echo "==> repository  $REPO"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${REPO%%/*}"

# --platform linux/arm64 is not optional. The task definition declares ARM64
# because Graviton is about 20% cheaper per vCPU-hour, and an amd64 image on it
# does not run slowly -- it fails to start with an exec format error.
#
# On an Apple Silicon Mac this is a native build. On an Intel one it runs under
# QEMU emulation and takes several minutes.
echo "==> building linux/arm64"
docker buildx build \
  --platform linux/arm64 \
  --tag "${REPO}:latest" \
  --provenance false \
  --push \
  "$ROOT"

echo "==> deploying"
# Stop-the-old-then-start-the-new, because the service runs a single task with
# no load balancer in front of it. Expect roughly a minute of 5xx.
aws ecs update-service \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --force-new-deployment \
  --output text --query 'service.deployments[0].id' >/dev/null

echo "==> waiting for the service to settle (a few minutes)"
aws ecs wait services-stable --region "$REGION" --cluster "$CLUSTER" --services "$SERVICE"

SITE_URL="$(terraform output -raw site_url)"
if [[ -n "$SITE_URL" ]]; then
  echo "==> live at $SITE_URL"
  echo "    origin record now resolves to: $(dig +short "$(terraform output -raw origin_record)" | tail -1)"
else
  # Phase one: no DNS name exists, and the task that just started has an address
  # the previous one did not. Ask ECS rather than printing a stale value.
  echo "==> live at $("$SCRIPT_DIR/task_ip.sh")"
fi
