# ── the origin record ───────────────────────────────────────────────────────
# CloudFront will not accept an IP address as a custom origin; it needs a
# hostname. A Fargate task's public IP is new on every deploy and again after
# every Spot reclaim. This record bridges the two, and the Lambda below keeps
# it honest.
#
# The address here is a placeholder that is true for about thirty seconds after
# the first apply. Terraform is told to stop looking at it after that, because
# the Lambda -- not this file -- is what owns the value from then on.
resource "aws_route53_record" "origin" {
  count   = var.enable_cdn ? 1 : 0
  zone_id = data.aws_route53_zone.this[0].zone_id
  name    = local.origin_domain
  type    = "A"
  ttl     = 60
  records = ["192.0.2.1"] # TEST-NET-1: routes nowhere, by RFC 5737

  lifecycle {
    ignore_changes = [records]
  }
}

data "archive_file" "origin_dns" {
  count       = var.enable_cdn ? 1 : 0
  type        = "zip"
  source_file = "${path.module}/lambda/origin_dns.py"
  output_path = "${path.module}/.build/origin_dns.zip"
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "origin_dns" {
  count              = var.enable_cdn ? 1 : 0
  name               = "${local.name}-origin-dns"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "origin_dns" {
  count = var.enable_cdn ? 1 : 0

  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:*"]
  }

  # DescribeNetworkInterfaces takes no resource condition -- the API has no
  # resource-level permissions -- so this is read-only and account-wide by
  # design, not by omission.
  statement {
    actions   = ["ec2:DescribeNetworkInterfaces"]
    resources = ["*"]
  }

  # Scoped to the one zone. A broader grant here would let this function
  # rewrite any DNS record in the account.
  statement {
    actions   = ["route53:ChangeResourceRecordSets"]
    resources = [data.aws_route53_zone.this[0].arn]
  }
}

resource "aws_iam_role_policy" "origin_dns" {
  count  = var.enable_cdn ? 1 : 0
  name   = "update-origin-record"
  role   = aws_iam_role.origin_dns[0].id
  policy = data.aws_iam_policy_document.origin_dns[0].json
}

resource "aws_cloudwatch_log_group" "origin_dns" {
  count             = var.enable_cdn ? 1 : 0
  name              = "/aws/lambda/${local.name}-origin-dns"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "origin_dns" {
  count            = var.enable_cdn ? 1 : 0
  function_name    = "${local.name}-origin-dns"
  role             = aws_iam_role.origin_dns[0].arn
  filename         = data.archive_file.origin_dns[0].output_path
  source_code_hash = data.archive_file.origin_dns[0].output_base64sha256
  handler          = "origin_dns.handler"
  runtime          = "python3.13"
  architectures    = ["arm64"]

  # The public IP is associated a beat after the task reports RUNNING, so the
  # function retries for a few seconds. 60 leaves room for that plus the
  # Route 53 call; the function runs a handful of times a month and is well
  # inside the Lambda free tier either way.
  timeout = 60

  environment {
    variables = {
      HOSTED_ZONE_ID = data.aws_route53_zone.this[0].zone_id
      ORIGIN_RECORD  = local.origin_domain
      RECORD_TTL     = "60"
    }
  }

  depends_on = [aws_cloudwatch_log_group.origin_dns]
}

# Fires when a task in this cluster reaches RUNNING. desiredStatus is matched
# as well as lastStatus: a task being torn down reports lastStatus RUNNING with
# desiredStatus STOPPED for a moment, and acting on that would point the record
# at the task that is going away.
resource "aws_cloudwatch_event_rule" "task_running" {
  count       = var.enable_cdn ? 1 : 0
  name        = "${local.name}-task-running"
  description = "ECS task reached RUNNING -- repoint the origin record"

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
    detail = {
      clusterArn    = [aws_ecs_cluster.this.arn]
      lastStatus    = ["RUNNING"]
      desiredStatus = ["RUNNING"]
    }
  })
}

resource "aws_cloudwatch_event_target" "origin_dns" {
  count     = var.enable_cdn ? 1 : 0
  rule      = aws_cloudwatch_event_rule.task_running[0].name
  target_id = "origin-dns"
  arn       = aws_lambda_function.origin_dns[0].arn
}

resource "aws_lambda_permission" "events" {
  count         = var.enable_cdn ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.origin_dns[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.task_running[0].arn
}

# ── the public records ──────────────────────────────────────────────────────
resource "aws_route53_record" "site" {
  for_each = var.enable_cdn ? toset(distinct([local.site_domain, "www.${var.domain_name}"])) : toset([])

  zone_id = data.aws_route53_zone.this[0].zone_id
  name    = each.value
  type    = "A"

  # An alias, not a CNAME: Route 53 charges nothing for alias queries to a
  # CloudFront distribution, and an apex domain cannot hold a CNAME at all.
  alias {
    name                   = aws_cloudfront_distribution.site[0].domain_name
    zone_id                = aws_cloudfront_distribution.site[0].hosted_zone_id
    evaluate_target_health = false
  }
}
