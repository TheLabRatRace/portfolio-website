locals {
  name = var.project

  # The container runs as an unprivileged uid, so it binds 5002 rather than 80.
  # Fargate does not support the systemControl that would lower the privileged
  # port floor, so this number is in the phase-one URL and in every rule below.
  container_port = 5002

  tags = {
    Project   = var.project
    ManagedBy = "terraform"
    Source    = "deploy/terraform"
  }

  site_domain   = var.domain_name == "" ? "" : (var.subdomain == "" ? var.domain_name : "${var.subdomain}.${var.domain_name}")
  origin_domain = var.domain_name == "" ? "" : "${var.origin_subdomain}.${var.domain_name}"
  # Where the admin app should point its "View ->" links. Explicit setting
  # wins; otherwise the public site's own address, once there is a stable one.
  # In phase one there is not: the public task's IP changes on every deploy,
  # so this stays empty and the admin templates omit the links rather than
  # linking somewhere that stopped being the site an hour ago.
  public_site_url = var.public_site_url != "" ? var.public_site_url : (var.enable_cdn ? "https://${local.site_domain}" : "")

  # The admin service is reached directly, always -- CloudFront fronts the
  # public site only, and putting a login form behind a CDN buys nothing.
  admin_cidrs = length(var.admin_allowed_cidrs) > 0 ? var.admin_allowed_cidrs : var.allowed_cidrs

  vpc_id     = var.vpc_id != "" ? var.vpc_id : data.aws_vpc.default[0].id
  subnet_ids = length(var.subnet_ids) > 0 ? var.subnet_ids : data.aws_subnets.public.ids
}

data "aws_vpc" "default" {
  count   = var.vpc_id == "" ? 1 : 0
  default = true
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  # A subnet that hands out public IPs is one with a route to the internet
  # gateway, which is the property the task actually needs: it is how the image
  # is pulled from ECR without paying for a NAT gateway.
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

data "aws_route53_zone" "this" {
  count        = var.enable_cdn ? 1 : 0
  name         = "${var.domain_name}."
  private_zone = false
}

# The published list of address ranges CloudFront uses to reach an origin. It
# is what makes a task with a public IP acceptable: the port is open to the CDN
# and closed to the rest of the internet, so nobody reaches the origin directly
# and no scanner ever sees an open port.
#
# The list holds roughly 55 entries and each counts against the 60-rule quota
# on a security group, so this group gets that one rule and nothing else.
data "aws_ec2_managed_prefix_list" "cloudfront" {
  count = var.enable_cdn ? 1 : 0
  name  = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "task" {
  name        = "${local.name}-task"
  description = "Fargate task: HTTP in from CloudFront only"
  vpc_id      = local.vpc_id
  tags        = { Name = "${local.name}-task" }
}

resource "aws_vpc_security_group_ingress_rule" "from_cloudfront" {
  count             = var.enable_cdn ? 1 : 0
  security_group_id = aws_security_group.task.id
  description       = "HTTP from CloudFront edge locations only"
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront[0].id
  ip_protocol       = "tcp"
  from_port         = local.container_port
  to_port           = local.container_port
}

# Phase one: no CloudFront yet, so the task is reached directly and the rule
# has to name whoever is allowed to do that. Mutually exclusive with the rule
# above -- turning the CDN on replaces this with the prefix list, which is a
# strictly smaller opening.
resource "aws_vpc_security_group_ingress_rule" "direct" {
  for_each = var.enable_cdn ? toset([]) : toset(var.allowed_cidrs)

  security_group_id = aws_security_group.task.id
  description       = "Direct HTTP to the task (no CDN in front yet)"
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = local.container_port
  to_port           = local.container_port
}

# Outbound is open: the task pulls from ECR, writes to CloudWatch Logs, reads
# and writes S3, and connects to RDS. Narrowing this needs the endpoints those
# services publish, and gains nothing that the closed inbound side has not
# already gained.
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.task.id
  description       = "ECR, CloudWatch Logs, S3, RDS"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# The point of running in the same VPC as the database: Postgres can now be
# reached by this one security group and by nothing else, which is the
# precondition for turning off the instance's public accessibility.
resource "aws_vpc_security_group_ingress_rule" "rds_from_task" {
  count                        = var.rds_security_group_id != "" ? 1 : 0
  security_group_id            = var.rds_security_group_id
  description                  = "Postgres from the ${local.name} Fargate task"
  referenced_security_group_id = aws_security_group.task.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
