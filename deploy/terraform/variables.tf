variable "project" {
  description = "Name prefix for every resource created here."
  type        = string
  default     = "portfolio"
}

variable "region" {
  description = <<-EOT
    Where the container runs. This must be the region the RDS instance is in.
    A cross-region hop costs a full round trip on every one of the queries a
    page makes, which is the difference between a 30 ms page and a 300 ms one.
  EOT
  type        = string
  default     = "us-east-2"
}

variable "enable_cdn" {
  description = <<-EOT
    Put CloudFront, a certificate and a DNS name in front of the task.

    false -- phase one -- is the task on its own: reachable at
    http://<public-ip>:5002, no TLS, and a new address after every deploy.
    Enough to see the site running on real infrastructure and to check that
    it talks to RDS from inside the VPC.

    true adds TLS, caching, a stable name and a security group that closes the
    origin to everything but CloudFront. It needs a Route 53 public hosted
    zone for domain_name; see "Phase two" in deploy/README.md for how to get
    one when the domain's DNS is at Namecheap.
  EOT
  type        = bool
  default     = false

  validation {
    condition     = !var.enable_cdn || var.domain_name != ""
    error_message = "enable_cdn = true needs domain_name set, and a Route 53 public hosted zone for it."
  }
}

variable "domain_name" {
  description = <<-EOT
    The registered domain, without a subdomain -- "example.com". Required only
    when enable_cdn is true, and a Route 53 public hosted zone for it must
    already exist; this configuration looks the zone up, it does not create it.
  EOT
  type        = string
  default     = ""
}

variable "allowed_cidrs" {
  description = <<-EOT
    Who may reach the task directly. Only consulted while enable_cdn is false;
    once CloudFront is in front, the security group is narrowed to its
    published origin ranges and this is ignored.

    The default is the whole internet, which is what "just use the public IP"
    means. Phase one has no TLS, so while it is open anyone on the path reads
    every request -- including an /admin/login password. Narrowing this to your
    own address is one line and worth it:

        allowed_cidrs = ["203.0.113.4/32"]
  EOT
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "subdomain" {
  description = <<-EOT
    Subdomain the site answers on, or "" to serve the apex. "www" is also
    always created and redirects are left to CloudFront's alternate names.
  EOT
  type        = string
  default     = ""
}

variable "origin_subdomain" {
  description = <<-EOT
    The internal name that points at the running task. CloudFront requires a
    domain name for a custom origin -- it will not accept a bare IP -- and the
    task's IP changes every deploy, so a Lambda rewrites this record whenever a
    task reaches RUNNING. Visitors never see it.
  EOT
  type        = string
  default     = "origin"
}

variable "use_spot" {
  description = <<-EOT
    Run on FARGATE_SPOT instead of FARGATE. Roughly 70% cheaper -- about $2.20
    a month instead of $7.20 -- in exchange for AWS being allowed to reclaim
    the task with two minutes' notice. With one task and no load balancer, a
    reclaim is a few minutes of downtime while a replacement starts and the DNS
    record catches up. Reasonable for a portfolio; not for anything on call.
  EOT
  type        = bool
  default     = false
}

variable "task_cpu" {
  description = "Fargate CPU units. 256 = 0.25 vCPU, the smallest billable size."
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "Fargate memory in MiB. 512 is the smallest legal pairing with 256 CPU."
  type        = number
  default     = 512
}

variable "vpc_id" {
  description = "VPC to run in. Empty uses the account's default VPC, which is where the RDS instance already lives."
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = <<-EOT
    Subnets for the task. Empty selects every public subnet in the VPC.

    They have to be public. The task pulls its image from ECR over the
    internet gateway, which is free; the alternative -- private subnets --
    needs either a NAT gateway ($32/mo before traffic) or three interface
    endpoints ($22/mo), each of them more than everything else here combined.
  EOT
  type        = list(string)
  default     = []
}

variable "rds_security_group_id" {
  description = <<-EOT
    Security group attached to the RDS instance. Given one, an ingress rule is
    added allowing 5432 from the task's security group and nothing else, which
    is what finally lets the database stop being publicly reachable. Leave
    empty to manage that rule by hand.
  EOT
  type        = string
  default     = ""
}

variable "assets_bucket" {
  description = "S3 bucket holding uploaded images. The task's IAM role is granted access to it, so no access key ever enters the container."
  type        = string
  default     = ""
}

variable "assets_public_base_url" {
  description = "Public base URL objects are served from (a CloudFront domain, or the bucket URL). Empty means every asset URL gets presigned."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention. Never expiring is the default AWS gives you and it bills for storage forever."
  type        = number
  default     = 14
}

variable "price_class" {
  description = "CloudFront edge coverage. PriceClass_100 is North America and Europe, and is the cheapest."
  type        = string
  default     = "PriceClass_100"
}

variable "admin_allowed_cidrs" {
  description = <<-EOT
    Who may reach the admin container, as CIDRs. Empty falls back to
    allowed_cidrs. This is the only thing standing in front of the login form
    -- keep it to the address you actually administer from, never 0.0.0.0/0.
  EOT
  type        = list(string)
  default     = []

  validation {
    condition     = !contains(var.admin_allowed_cidrs, "0.0.0.0/0")
    error_message = "Refusing 0.0.0.0/0 on the admin service. Name your own address."
  }
}

variable "admin_task_cpu" {
  description = "CPU units for the admin task. It serves one person."
  type        = string
  default     = "256"
}

variable "admin_task_memory" {
  description = "Memory (MiB) for the admin task."
  type        = string
  default     = "512"
}

variable "public_site_url" {
  description = <<-EOT
    Absolute URL of the public site, for the admin app's "View ->" links.
    Empty and no CDN means there is no stable public address yet (a phase-one
    task IP changes on every deploy), and the admin app omits those links.
  EOT
  type        = string
  default     = ""
}

variable "enable_static_cdn" {
  description = <<-EOT
    Create the static-asset bucket and its CloudFront distribution, and point
    both containers at it. Independent of enable_cdn: this one needs no domain
    and no certificate, so it is worth having in phase one, where the site is
    still a bare IP address.
  EOT
  type        = bool
  default     = true
}

variable "static_bucket" {
  description = "Name for the static-asset bucket. Empty means <project>-static."
  type        = string
  default     = ""
}

variable "static_base_url" {
  description = <<-EOT
    Override the URL the app builds static asset links from. Normally empty --
    the distribution created here supplies it. Set it to point at a bucket this
    configuration does not manage, or to "" with enable_static_cdn = false to
    have the container serve its own assets again.
  EOT
  type        = string
  default     = ""
}
