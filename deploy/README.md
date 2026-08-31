# Deploying to ECS

Single-task Fargate service on Graviton, in the same region as the database.
It ships in two phases, and the second one is a variable flip rather than a
rebuild.

| | what you get | what it costs on top of RDS |
|---|---|---|
| **Phase one** — `enable_cdn = false` (the default) | The task on its own, at `http://<public-ip>:5002`. No domain, no TLS, a new address after every deploy. | **~$11/mo**, or ~$6 on Spot |
| **Phase two** — `enable_cdn = true` | CloudFront, a free ACM certificate, `https://<your-domain>`, `/static/*` cached at the edge, a stable address. | **~$11.50/mo**, or ~$6.50 on Spot |

Phase two is not meaningfully more expensive — CloudFront and ACM are free at
this volume and the Route 53 zone is $0.50. What it costs is a prerequisite:
a Route 53 hosted zone. Your DNS is at Namecheap, so [that section](#phase-two-getting-a-name-in-front-of-it)
is the part to read when you are ready.

Everything is in `deploy/terraform`. Nothing outside `deploy/` is
deployment-specific except three environment variables the task sets.

---

## Phase one: the shape of it

```
        you
         │  http :5002   ← plaintext, and the address changes every deploy
         ▼
 ┌──────────────────┐   0.25 vCPU / 0.5 GB, ARM64, public subnet, public IP.
 │  Fargate task    │   Security group opens 5002 to allowed_cidrs.
 │  gunicorn        │
 └────────┬─────────┘
          │  :5432, private, same VPC
          ▼
 ┌──────────────────┐
 │  RDS Postgres    │   already running; this only adds a security-group rule
 └──────────────────┘
```

`deploy/scripts/task_ip.sh` prints the current address. There is nothing to
write down: a Fargate task cannot hold an Elastic IP, so the address is
assigned at task start and is different after the next deploy.

### Phase one has no TLS. Two consequences.

**Do not log into `/admin` over it.** The login form posts a password in the
clear to a public IP. Edit content locally against the same RDS instance
instead — the local app and the task share a database, so anything you change
locally is live immediately.

The task definition reflects this: `SESSION_COOKIE_SECURE` is off while
`enable_cdn` is false. It has to be. A `Secure` cookie on a plain-http site is
one the browser accepts and then never sends back, so the login would appear to
succeed and bounce straight back to the form. `TRUSTED_PROXY_HOPS` is `0` for
the same class of reason: with nothing in front of the container, an
`X-Forwarded-For` header is just a value the caller chose.

**Narrow `allowed_cidrs` while you are testing.** The default is `0.0.0.0/0`,
which is the whole internet. Your own address only:

```bash
curl -s ifconfig.me
```

then put `["<that>/32"]` in `terraform.tfvars` and re-apply.

---

## What it costs

`us-east-2`, 730 hours. **Verify against the current pricing pages** — these
are estimates and AWS moves them.

| | phase one | phase two | Spot (either) |
|---|---:|---:|---:|
| Fargate 0.25 vCPU ARM | $5.91 | $5.91 | ~$1.80 |
| Fargate 0.5 GB ARM | $1.30 | $1.30 | ~$0.40 |
| Public IPv4 address | $3.65 | $3.65 | $3.65 |
| Route 53 hosted zone | — | $0.50 | +$0.50 |
| CloudFront | — | $0.00 (free tier: 1 TB + 10M requests) | $0.00 |
| ACM certificate | — | $0.00 | $0.00 |
| ECR storage (5 images, deduped) | ~$0.06 | ~$0.06 | ~$0.06 |
| CloudWatch Logs (14-day) | ~$0.05 | ~$0.05 | ~$0.05 |
| SSM Parameter Store, EventBridge, Lambda | $0.00 | $0.00 | $0.00 |
| **subtotal** | **~$10.97** | **~$11.47** | **~$6.46** |
| existing RDS db.t4g.micro + 20 GB | ~$13–15 | ~$13–15 | ~$13–15 |
| **all in** | **~$25/mo** | **~$25/mo** | **~$20/mo** |

The RDS instance is the largest line on the bill, and it was there before this.
Nothing in this directory changes it.

### What was deliberately not built

| | why not |
|---|---|
| Application Load Balancer, **$16.43/mo** + LCUs | The single largest avoidable cost, and for one task it buys only the DNS update that a Lambda does for free in phase two. See the tradeoff below. |
| NAT gateway, **$32.85/mo** + $0.045/GB | Only needed to put the task in a private subnet. It would cost three times the entire rest of this stack to hide an origin that the security group already closes. |
| VPC interface endpoints, **~$22/mo** | The other way to reach ECR from a private subnet. Same objection. |
| Secrets Manager, **$0.40/secret/mo** | SSM Parameter Store SecureString does the identical job for ECS and is free. Rotation is what the extra money buys, and nothing here rotates on a schedule. |
| Container Insights, **$0.30/custom metric/mo** | The monitoring would have cost more than the compute. |
| An Elastic IP for the task | Not possible. Fargate does not support it at any price. |

---

## Prerequisites

- AWS credentials with permission to create ECS, ECR, IAM, CloudFront, ACM,
  Route 53, Lambda, EventBridge, SSM and VPC security-group resources.
  **The S3 upload user whose key sits in the repository root is not one of
  them** — it was already shown to lack even `rds:DescribeDBInstances`. Use an
  administrative identity for the apply.
- `terraform` >= 1.9, `docker` with `buildx`, `aws` CLI v2.
- Phase one needs no domain at all.

---

## Running phase one, in order

The order matters in one place: the secrets have to exist before the first
`apply`, because Terraform reads them to get their ARNs.

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars          # allowed_cidrs at minimum
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

**2 — create the infrastructure.** A couple of minutes; there is no ACM
validation or CloudFront distribution to wait on in phase one.

```bash
terraform init
terraform apply
```

**3 — build and ship the image.** The first apply leaves the service with
nothing to pull, so the task will be failing until this runs.

```bash
../scripts/build_and_push.sh
```

It prints the address at the end. Build it for **arm64** — the script does. An
amd64 image on a Graviton task does not run slowly, it fails to start with an
exec format error.

**4 — look at it.**

```bash
open "$(deploy/scripts/task_ip.sh)"
```

**5 — close the database.** Once traffic is served from the task, the RDS
instance no longer needs to be reachable from the internet. This is the pending
item from earlier, and running in-VPC is what finally makes it possible.

- Set `rds_security_group_id` in `terraform.tfvars` and re-apply. That opens
  5432 to the task's security group specifically.
- Then remove the `0.0.0.0/0` rule on 5432, and set the instance to
  **Publicly accessible: No** in the RDS console.

Creating the first admin user is deliberately not on this list — it needs a
password over the wire, so leave it until phase two. If you want it sooner, do
it through ECS Exec, which is an outbound channel and not a listening port:

```bash
aws ecs execute-command --region us-east-2 \
  --cluster portfolio --task "$(aws ecs list-tasks --cluster portfolio \
    --query 'taskArns[0]' --output text)" \
  --container web --interactive --command "/bin/bash"
```

---

## Phase two: getting a name in front of it

```
        visitor
           │  https
           ▼
   ┌──────────────────┐   TLS terminates here. Free ACM certificate, free tier
   │   CloudFront     │   covers 1 TB/month, /static/* is cached at the edge.
   └────────┬─────────┘
            │  http :5002, to origin.<domain>
            ▼
   ┌──────────────────┐   security group now accepts CloudFront's ranges and
   │  Fargate task    │   nothing else — allowed_cidrs stops being consulted
   └──────────────────┘

   task reaches RUNNING ──► EventBridge ──► Lambda ──► Route 53 A record
```

That last line is the whole trick. CloudFront needs a *hostname* for its origin
— it will not accept an IP — and the task's public IP is new on every deploy. A
twelve-line Lambda writes the current IP into `origin.<domain>` whenever a task
starts. That is the only job a load balancer would be doing here, and it costs
nothing instead of $16 a month.

### Your DNS is at Namecheap. Three ways to do this.

The code as written needs `domain_name` to have a **Route 53 public hosted
zone**, because it does three things Namecheap cannot: prove domain ownership
to ACM automatically, write the origin record from a Lambda on every deploy,
and alias the apex at CloudFront.

**Option A — move DNS to Route 53.** Create the hosted zone, copy your existing
Namecheap records into it, then set Namecheap's nameservers to the four Route 53
gives you. The domain stays registered at Namecheap; only resolution moves.
`enable_cdn = true`, `terraform apply`, done — everything here works unchanged.
$0.50/month. This is the one to pick unless you have a reason not to.

**Option B — delegate one subdomain.** Keep Namecheap authoritative for the
domain and hand it only `origin.<domain>`: create a Route 53 zone for that
subdomain and add its four nameservers as `NS` records at Namecheap. The Lambda
then owns the record it needs and nothing else. You would still add the ACM
validation `CNAME` and the site's `CNAME` to CloudFront by hand at Namecheap,
and `dns.tf` needs the site records dropped. More moving parts, same price.

**Option C — no Route 53 at all.** Namecheap has a Dynamic DNS API
(`https://dynamicdns.park-your-domain.com/update?host=&domain=&password=&ip=`).
The Lambda calls that instead of Route 53, you add the ACM validation `CNAME`
by hand once, and point the apex at CloudFront with Namecheap's `ALIAS` record.
$0/month and no Route 53, at the cost of a per-vendor Lambda and a DDNS
password in Parameter Store. Say the word and I will write it.

Under A, the whole of phase two is:

```bash
$EDITOR terraform.tfvars     # enable_cdn = true, domain_name = "..."
terraform apply
```

Ten to fifteen minutes, most of it CloudFront. `terraform output site_url`
then answers.

### The plaintext origin hop

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

### Spot, or not — either phase

`use_spot = true` takes the compute from $7.21 to about $2.20. In exchange AWS
may reclaim the task on two minutes' notice; with one task and no load
balancer that is a few minutes of downtime while a replacement starts. Flip the
variable and re-apply — it is not a rebuild.

---

## The admin app

Admin is a **separate ECS service**, running the same image with `APP_ROLE=admin`,
scaled to zero.

Two things follow, and both are the point:

* **The public container has no `/admin` routes.** Not hidden behind a login —
  absent. That process never registered the admin blueprint, so `/admin/login`
  on the public site is a 404 from the URL map. There is no session check to
  get wrong and no decorator to forget.
* **The admin container is not running.** Most of the time the login form does
  not exist anywhere on the internet. Bringing it up is a deliberate act.

It has its own security group (`admin_allowed_cidrs`, falling back to
`allowed_cidrs`) and its own opening on the database, so admin access can be
revoked without touching the public site's.

```bash
bash deploy/scripts/admin_up.sh     # ~90 seconds, prints the URL
# ... edit ...
bash deploy/scripts/admin_down.sh   # back to zero
```

| | |
|---|---|
| Idle | **$0** — no task, no IP, nothing but log storage |
| Running | ~$0.011/hour (0.25 vCPU ARM, 0.5 GB, plus the IPv4 hour) |
| Cold start | 60–90 seconds: schedule, pull, boot, health check |

`desired_count` on this service is under `ignore_changes`. It is operational
state, not configuration — otherwise the next `terraform apply` would shut the
admin down in the middle of an edit.

**The address is new every time.** A Fargate task cannot hold an Elastic IP, so
`admin_up.sh` prints the address it got rather than expecting you to know one.

**There is no TLS in front of it, in either phase.** CloudFront fronts the
public site only; putting a login form behind a CDN buys nothing. The password
crosses the network in the clear — bring it up from a network you trust, and
put it down afterwards. If that stops being acceptable, the fix is an ALB with
ACM in front of this service (+$16.43/mo), not a CloudFront behavior.

**"View →" links.** The admin app has no public blueprints, so it cannot build
a link to a published page with `url_for`. It uses `PUBLIC_SITE_URL` instead,
set from `public_site_url` — or derived from the site domain once the CDN is
on. In phase one there is no stable public address to set (the task IP changes
on every deploy), so it stays empty and the links are simply not rendered.

**A shell in the admin task** — for `flask create-admin` and migrations:

```bash
aws ecs execute-command --cluster portfolio --task <task-arn> --container admin --interactive --command /bin/bash
```

---

## Static assets

CSS, JS and images are ~19 MB across ~2,000 files, and none of it is work a
0.25 vCPU container should be doing. `enable_static_cdn` (on by default)
creates a private S3 bucket and a CloudFront distribution in front of it, and
sets `STATIC_BASE_URL` in both task definitions to the distribution's URL.

With it set, every `<link>`, `<script>` and `<img>` on the page is an absolute
URL at the edge and the origin never sees the request. With it empty -- locally,
or with `enable_static_cdn = false` -- the same template calls fall back to
`url_for('static', ...)` and Flask serves the bytes exactly as before. Nothing
in the templates knows which one is happening.

Upload after any change to CSS, JS or images:

```bash
bash deploy/scripts/sync_static.sh
```

That rebuilds `style.min.css`, syncs the directory with `--delete`, and issues
one `/*` invalidation. Run it **before** the deploy that ships the HTML pointing
at the new files, never after -- assets first, then the page that asks for them.

Two things worth knowing about the caching:

- CSS and JS are requested with `?v=<sha256 prefix>` of their contents, so a
  changed file is a URL no browser has seen and a one-year `max-age` is safe.
  That digest does *not* protect CloudFront: the managed CachingOptimized
  policy leaves query strings out of its cache key. The invalidation is what
  covers the edge.
- Images have no digest, so they get a week rather than a year. An invalidation
  clears CloudFront but never reaches a browser that already has the file.

The bucket is private -- reachable only through the distribution, by an origin
access control scoped to that one distribution's ARN. There is no public URL
that bypasses the cache, and nothing can be pulled straight out of S3 on your
bandwidth bill. It is also a *different* bucket from the assets bucket that
holds uploads, and that is not tidiness: `sync_static.sh` runs `--delete`, and
pointed at a bucket holding uploads it would delete content the repo has never
seen.

Cost is rounding error: ~20 MB of storage is about $0.0005/month, and
CloudFront's perpetual free tier covers 1 TB out and 10M requests. The first
1,000 invalidation paths each month are free, and `/*` counts as one path.

## Afterwards

**Ship a code change** — push and roll, Terraform not involved:

```bash
deploy/scripts/build_and_push.sh
```

Expect roughly a minute of 5xx, and in phase one a new address afterwards. The
service stops the old task before starting the new one, because with one task
and no load balancer there is no way to overlap them usefully: ECS would tear
the old one down the instant the new one reported healthy, well before anything
pointed at it. Overlapping would buy a doubled bill and the same blip.

**Rotate a secret** — re-run `put_secrets.sh`, then `build_and_push.sh`.
Secrets resolve at task start, so a running task keeps the old value.

**Read the logs:**

```bash
aws logs tail /ecs/portfolio --follow --region us-east-2
```

**See which address is live:** `deploy/scripts/task_ip.sh` in phase one,
`dig +short origin.<your-domain>` in phase two.

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

**Phase one already delivers that**, and it is the larger half. Phase two adds
CloudFront, which removes the static assets from the origin's work entirely and
puts the TLS handshake at an edge near the visitor rather than in Ohio.

Sub-millisecond end to end is still not a thing anyone can deliver over the
public internet — the speed of light to the nearest edge is the floor — but a
warm page in the tens of milliseconds is.

---

## Notes on things that will bite

- **Phase one is http.** Repeated because it is the thing that will actually
  cost you something: do not type a password into it.
- **The port is in the URL.** `:5002`, because the container runs as an
  unprivileged uid and Fargate does not support the systemControl that would
  let it bind 80. CloudFront hides this in phase two.
- **The CloudFront prefix list has ~55 entries and a security group allows 60
  rules.** In phase two that one ingress rule nearly fills the group. Do not
  add more prefix-list rules to it.
- **Terraform state holds every attribute in plaintext.** It is gitignored.
  Keep it, or move to an S3 backend with encryption if this ever has more than
  one operator.
- **`terraform.tfvars` is gitignored**; `terraform.tfvars.example` is not.
- **The provider lock file *is* committed** on purpose, so an apply next year
  resolves the same provider versions.
- **The access-key CSV in the repository root is not needed in production.**
  The task reads S3 through its IAM role. It was also being baked into every
  image by `COPY . .`; `.dockerignore` now excludes it. A layer is not deleted
  by a later `rm` — it stays in the tarball — so any image built before this
  change still contains it and should not be pushed anywhere.
