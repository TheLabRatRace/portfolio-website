#!/usr/bin/env bash
#
# Print the address the site is answering on right now.
#
# A Fargate task cannot hold an Elastic IP. Its public address is assigned when
# the task starts and is a different address after the next deploy, so there is
# nothing to write down -- ask ECS each time. This is the phase-one substitute
# for a DNS name; once enable_cdn is on, the CloudFront domain is stable and
# `terraform output site_url` is the answer instead.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../terraform"

REGION="$(terraform output -raw region 2>/dev/null || echo "${AWS_REGION:-us-east-2}")"
CLUSTER="$(terraform output -raw cluster_name)"
# Optional argument: which service to ask about. Defaults to the public site;
# admin_up.sh passes the admin service so there is one copy of this lookup.
SERVICE="${1:-$(terraform output -raw service_name)}"
PORT="$(terraform output -raw container_port 2>/dev/null || echo 5002)"

TASK="$(aws ecs list-tasks \
  --region "$REGION" --cluster "$CLUSTER" --service-name "$SERVICE" \
  --desired-status RUNNING \
  --output text --query 'taskArns[0]')"

if [[ -z "$TASK" || "$TASK" == "None" ]]; then
  echo "No running task. Check: aws ecs describe-services --cluster $CLUSTER --services $SERVICE" >&2
  exit 1
fi

# The ENI id is buried in the task's attachment details as a name/value list,
# which is why this is a query and not a field read.
ENI="$(aws ecs describe-tasks \
  --region "$REGION" --cluster "$CLUSTER" --tasks "$TASK" \
  --output text \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value | [0]')"

IP="$(aws ec2 describe-network-interfaces \
  --region "$REGION" --network-interface-ids "$ENI" \
  --output text --query 'NetworkInterfaces[0].Association.PublicIp')"

if [[ -z "$IP" || "$IP" == "None" ]]; then
  echo "Task $TASK has no public IP. Is it in a public subnet with assign_public_ip on?" >&2
  exit 1
fi

echo "http://${IP}:${PORT}"
