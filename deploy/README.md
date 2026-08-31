# Deploying to ECS

Single-task Fargate service on Graviton, in the same region as the database,
with CloudFront in front of it. About **$11.50 a month** on-demand, or **$6.40**
on Spot, on top of the RDS instance that is already running.

Everything is in `deploy/terraform`. Nothing outside `deploy/` is
deployment-specific except three environment variables the task sets.

---

## The shape of it

```
        visitor
           │  https
           ▼
   ┌──────────────────┐   TLS terminates here. Free ACM certificate, free tier
   │   CloudFront     │   covers 1 TB/month, /static/* is cached at the edge.
   └────────┬─────────┘
            │  http :5002, to origin.<domain>
            ▼
   ┌──────────────────┐   0.25 vCPU / 0.5 GB, ARM64, public subnet, public IP.
   │  Fargate task    │   Security group accepts CloudFront's ranges and
   │  gunicorn        │   nothing else.
   └────────┬─────────┘
            │  :5432, private, same VPC
            ▼
   ┌──────────────────┐
   │  RDS Postgres    │   already running; this only adds a security-group rule
   └──────────────────┘

   task reaches RUNNING ──► EventBridge ──► Lambda ──► Route 53 A record
```

That last line is the whole trick. CloudFront needs a *hostname* for its origin
— it will not accept an IP — and a Fargate task's public IP is new on every
deploy. A twelve-line Lambda writes the current IP into `origin.<domain>`
whenever a task starts. That is the only job a load balancer would be doing
here, and it costs nothing instead of $16 a month.

---

## What it costs

`us-east-2`, 730 hours. **Verify against the current pricing pages** — these
are estimates and AWS moves them.

| | on-demand | Spot |
|---|---:|---:|
| Fargate 0.25 vCPU ARM | $5.91 | ~$1.80 |
| Fargate 0.5 GB ARM | $1.30 | ~$0.40 |
| Public IPv4 address | $3.65 | $3.65 |
| Route 53 hosted zone | $0.50 | $0.50 |
| CloudFront | $0.00 (free tier: 1 TB + 10M requests) | $0.00 |
| ACM certificate | $0.00 | $0.00 |
| ECR storage (5 images, deduped) | ~$0.06 | ~$0.06 |
| CloudWatch Logs (14-day) | ~$0.05 | ~$0.05 |
| SSM Parameter Store, EventBridge, Lambda | $0.00 | $0.00 |
| **subtotal** | **~$11.47** | **~$6.46** |
| existing RDS db.t4g.micro + 20 GB | ~$13–15 | ~$13–15 |
| **all in** | **~$25/mo** | **~$20/mo** |

The RDS instance is now the largest line on the bill, and it was there before
this. Nothing in this directory changes it.

### What was deliberately not built

| | why not |
|---|---|
| Application Load Balancer, **$16.43/mo** + LCUs | The single largest avoidable cost, and for one task it buys only the DNS update that the Lambda already does. See the tradeoff below. |
| NAT gateway, **$32.85/mo** + $0.045/GB | Only needed to put the task in a private subnet. It would cost three times the entire rest of this stack to hide an origin that the security group already closes. |
| VPC interface endpoints, **~$22/mo** | The other way to reach ECR from a private subnet. Same objection. |
| Secrets Manager, **$0.40/secret/mo** | SSM Parameter Store SecureString does the identical job for ECS and is free. Rotation is what the extra money buys, and nothing here rotates on a schedule. |
| Container Insights, **$0.30/custom metric/mo** | The monitoring would have cost more than the compute. |

---

## Two things to decide before you run it

### 1. Spot, or not

`use_spot = true` takes the compute from $7.21 to about $2.20. In exchange AWS
may reclaim the task on two minutes' notice; with one task and no load
balancer that is a few minutes of downtime while a replacement starts and DNS
catches up. Reasonable for a portfolio. Flip the variable and re-apply — it is
not a rebuild.

### 2. The plaintext origin hop

CloudFront speaks **http** to the task, so the hop from the CloudFront edge to
us-east-2 is unencrypted. Visitors always see https; this is behind that.

It cannot easily be otherwise without a load balancer: a certificate for the
origin hostname would have to live inside the container, ACM will not export
one, and CloudFront refuses a self-signed origin.

What contains it:

- The task's security group accepts traffic only from CloudFront's published
  origin-facing address ranges, so the origin is not directly reachable and
  never turns up in a port scan.
- What is left is an attacker on the network path between a CloudFront edge
  and us-east-2 — a network-level adversary, not a passerby.

**This matters most for `/admin/login`,** which posts a password. If that
residual risk is not acceptable, the fix is an ALB with an ACM certificate in
front of the task: it ends the plaintext hop, removes the Lambda and the origin
record entirely, and costs about $16 a month. Say so and it is a contained
change to `ecs.tf` and `cloudfront.tf`.

A cheaper partial hardening, if you want it: have CloudFront inject a secret
header and reject requests without it. That closes the one hole the security
group leaves — somebody pointing *their own* CloudFront distribution at your
origin — but does nothing about the plaintext.

---

## Prerequisites

- A domain with a **Route 53 public hosted zone**. Not optional: TLS needs a
  certificate, a certificate needs a name you control, and CloudFront needs a
  stable origin hostname. All three come from the zone.
- AWS credentials with permission to create ECS, ECR, IAM, CloudFront, ACM,
  Route 53, Lambda, EventBridge, SSM and VPC security-group resources.
  **The S3 upload user whose key sits in the repository root is not one of
  them** — it was already shown to lack even `rds:DescribeDBInstances`. Use an
  administrative identity for the apply.
- `terraform` >= 1.6, `docker` with `buildx`, `aws` CLI v2.

---

## Running it, in order

The order matters in one place: the secrets have to exist before the first
`apply`, because Terraform reads them to get their ARNs.

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars          # domain_name at minimum
```

**1 — secrets into Parameter Store.** Reads your gitignored `.env`; prints
nothing. It also refuses a `DATABASE_URL` that would make the app refuse to
boot, which on ECS is otherwise a crash loop with the reason buried in
CloudWatch.

```bash
PROJECT=portfolio AWS_REGION=us-east-2 ../scripts/put_secrets.sh
```

`DATABASE_URL` must end in
`?sslmode=verify-full&sslrootcert=/app/certs/global-bundle.pem` — that is where
the bundle lives *inside the image*, and a host path resolves to nothing there.

**2 — create the infrastructure.** ACM validation is the slow part; ten to
fifteen minutes total is normal, most of it CloudFront.

```bash
terraform init
terraform apply
```

**3 — build and ship the image.** The first apply leaves the service with
nothing to pull, so the task will be failing until this runs.

```bash
../scripts/build_and_push.sh
```

Build it for **arm64** — the script does. An amd64 image on a Graviton task
does not run slowly, it fails to start with an exec format error.

**4 — create the first admin user** in the running task. No bastion, no SSH
key, no open port; ECS Exec is an outbound channel.

```bash
aws ecs execute-command --region us-east-2 \
  --cluster portfolio --task "$(aws ecs list-tasks --cluster portfolio \
    --query 'taskArns[0]' --output text)" \
  --container web --interactive --command "/bin/bash"
```

**5 — close the database.** Once traffic is served from the task, the RDS
instance no longer needs to be reachable from the internet. This is the pending
item from earlier, and running in-VPC is what finally makes it possible.

- Set `rds_security_group_id` in `terraform.tfvars` and re-apply. That opens
  5432 to the task's security group specifically.
- Then remove the `0.0.0.0/0` rule on 5432, and set the instance to
  **Publicly accessible: No** in the RDS console.

---

## Afterwards

**Ship a code change** — push and roll, Terraform not involved:

```bash
deploy/scripts/build_and_push.sh
```

Expect roughly a minute of 5xx. The service stops the old task before starting
the new one, because with one task and no load balancer there is no way to
overlap them usefully: ECS would tear the old one down the instant the new one
reported healthy, well before the 60-second DNS record caught up. Overlapping
would buy a doubled bill and the same blip.

**Rotate a secret** — re-run `put_secrets.sh`, then `build_and_push.sh`.
Secrets resolve at task start, so a running task keeps the old value.

**Read the logs:**

```bash
aws logs tail /ecs/portfolio --follow --region us-east-2
```

**See which IP is live:** `dig +short origin.<your-domain>`

**Tear it all down:**

```bash
cd deploy/terraform && terraform destroy
```

That removes everything here. It does not touch the RDS instance or the S3
bucket, neither of which Terraform created. The ECR repository will refuse to
delete while it holds images — empty it first, or add `force_delete = true`.

---

## Latency

The site currently answers from a laptop in one region against a database in
another, and roughly 250 of the 270 ms a `/projects/` request takes is round
trips to us-east-2 rather than work. Running the app *in* us-east-2 collapses
each of those round trips from ~62 ms to well under 1 ms, which is the actual
remaining fix for the page-load complaint — the query count was cut from 14 to
2 already, and 2 × 1 ms is a different page from 2 × 62 ms.

CloudFront then removes the static assets from the origin's work entirely.

Sub-millisecond end to end is still not a thing anyone can deliver over the
public internet — the speed of light to the nearest CloudFront edge is the
floor — but a warm page in the tens of milliseconds is.

---

## Notes on things that will bite

- **The CloudFront prefix list has ~55 entries and a security group allows 60
  rules.** That one ingress rule nearly fills the group. Do not add more
  prefix-list rules to it.
- **Terraform state holds every attribute in plaintext.** It is gitignored.
  Keep it, or move to an S3 backend with encryption if this ever has more than
  one operator.
- **`terraform.tfvars` is gitignored**; `terraform.tfvars.example` is not.
- **The provider lock file `is` committed** on purpose, so an apply next year
  resolves the same provider versions.
- **The access-key CSV in the repository root is not needed in production.**
  The task reads S3 through its IAM role. It was also being baked into every
  image by `COPY . .`; `.dockerignore` now excludes it. A layer is not deleted
  by a later `rm` — it stays in the tarball — so any image built before this
  change still contains it and should not be pushed anywhere.
