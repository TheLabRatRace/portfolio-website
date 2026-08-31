#!/usr/bin/env bash
#
# Bring the admin app up, print its address, and remind you to put it away.
#
# The admin service sits at desired_count 0. Most of the time the login form is
# not running anywhere -- there is no host answering for it, which is a much
# stronger statement than a login form that is running and rejecting people.
# This raises it to one task, waits for the task to be reachable, and tells you
# where it is. It costs roughly a cent an hour while it is up.
#
# Put it back with admin_down.sh when you are finished.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../terraform"

REGION="$(terraform output -raw region 2>/dev/null || echo "${AWS_REGION:-us-east-2}")"
CLUSTER="$(terraform output -raw cluster_name)"
SERVICE="$(terraform output -raw admin_service_name)"

echo "Scaling $SERVICE to 1 task..."
aws ecs update-service \
  --region "$REGION" --cluster "$CLUSTER" --service "$SERVICE" \
  --desired-count 1 >/dev/null

# A cold Fargate task is roughly 60-90 seconds: schedule, pull the image, start
# gunicorn, pass a health check. services-stable waits for all of that, and for
# the deployment to settle, rather than for the task to merely exist.
echo "Waiting for the task to start (this takes about 90 seconds)..."
aws ecs wait services-stable \
  --region "$REGION" --cluster "$CLUSTER" --services "$SERVICE"

URL="$("$SCRIPT_DIR/task_ip.sh" "$SERVICE")"

cat <<EOM

Admin is up:  ${URL}/admin/login

Reachable only from the addresses in admin_allowed_cidrs (or allowed_cidrs).
The address is new every time -- a Fargate task cannot hold a fixed IP.

There is no TLS in front of this. The password crosses the network in the
clear, so bring it up from a network you trust and put it down after:

    bash deploy/scripts/admin_down.sh
EOM
