#!/usr/bin/env bash
#
# Put the admin app away: back to zero tasks, back to nothing running.
#
# Safe to run at any time, including when it is already down.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../terraform"

REGION="$(terraform output -raw region 2>/dev/null || echo "${AWS_REGION:-us-east-2}")"
CLUSTER="$(terraform output -raw cluster_name)"
SERVICE="$(terraform output -raw admin_service_name)"

aws ecs update-service \
  --region "$REGION" --cluster "$CLUSTER" --service "$SERVICE" \
  --desired-count 0 >/dev/null

echo "$SERVICE scaled to 0. The admin login form is not running anywhere."
