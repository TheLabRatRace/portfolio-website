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

variable "domain_name" {
  description = <<-EOT
    The registered domain, without a subdomain -- "example.com". A Route 53
    public hosted zone for it must already exist; this configuration looks it
    up, it does not create it.

    The domain is not optional. TLS requires a certificate, a certificate
    requires a name you control, and this design also needs a stable hostname
    to point CloudFront at (a Fargate task's public IP changes on every
    deploy). Both come from the zone.
  EOT
  type        = string
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
