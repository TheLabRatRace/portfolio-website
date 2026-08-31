"""Point the origin DNS record at whichever task is currently running.

CloudFront needs a hostname for its origin and will not take an IP address. A
Fargate task's public IP is new on every deploy and again after every Spot
reclaim. EventBridge sees the task reach RUNNING and calls this; this writes
the address into Route 53.

That is the whole of what a $16-a-month load balancer would otherwise be doing
for a single-task service.
"""

import os
import time

import boto3

HOSTED_ZONE_ID = os.environ["HOSTED_ZONE_ID"]
ORIGIN_RECORD = os.environ["ORIGIN_RECORD"]
RECORD_TTL = int(os.environ.get("RECORD_TTL", "60"))

ec2 = boto3.client("ec2")
route53 = boto3.client("route53")


def _network_interface_id(detail):
    for attachment in detail.get("attachments", []):
        if attachment.get("type") != "eni":
            continue
        for item in attachment.get("details", []):
            if item.get("name") == "networkInterfaceId":
                return item.get("value")
    return None


def _public_ip(eni_id, attempts=6, delay=2):
    """Wait for the address to be associated.

    The task reports RUNNING as soon as the container starts, which is a moment
    before the public IP is attached to the ENI. Giving up on the first empty
    read would leave the record pointing at the task that just went away --
    which is the site being down, not a missed optimisation. So it waits.
    """
    for attempt in range(attempts):
        interfaces = ec2.describe_network_interfaces(NetworkInterfaceIds=[eni_id])
        association = interfaces["NetworkInterfaces"][0].get("Association", {})
        ip = association.get("PublicIp")
        if ip:
            return ip
        if attempt < attempts - 1:
            time.sleep(delay)
    return None


def handler(event, context):
    detail = event.get("detail", {})

    # The EventBridge rule filters for this already. Checked again here because
    # a rule is edited in a console by someone who has forgotten why it is
    # narrow, and the failure -- the record aimed at a task that is shutting
    # down -- looks like a random outage rather than a bad event filter.
    if detail.get("lastStatus") != "RUNNING" or detail.get("desiredStatus") != "RUNNING":
        return {"skipped": "not a starting task", "task": detail.get("taskArn")}

    eni_id = _network_interface_id(detail)
    if not eni_id:
        return {"skipped": "no eni in event", "task": detail.get("taskArn")}

    ip = _public_ip(eni_id)
    if not ip:
        raise RuntimeError(
            f"{eni_id} still has no public IP. The task is running in a subnet "
            "that does not assign one, or assign_public_ip is off -- either "
            "way CloudFront has no origin to reach."
        )

    route53.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch={
            "Comment": f"task {detail.get('taskArn', '?').rsplit('/', 1)[-1]}",
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": ORIGIN_RECORD,
                        "Type": "A",
                        "TTL": RECORD_TTL,
                        "ResourceRecords": [{"Value": ip}],
                    },
                }
            ],
        },
    )

    print(f"{ORIGIN_RECORD} -> {ip}")
    return {"record": ORIGIN_RECORD, "ip": ip}
