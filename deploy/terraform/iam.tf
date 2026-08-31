data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# ── execution role ──────────────────────────────────────────────────────────
# Used by the ECS agent, before the container exists: pull the image, open the
# log stream, resolve the secrets. Not available to the application.
resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "read_secrets" {
  statement {
    actions = ["ssm:GetParameters"]
    resources = [
      data.aws_ssm_parameter.secret_key.arn,
      data.aws_ssm_parameter.database_url.arn,
    ]
  }

  # SecureString is encrypted under the account's default SSM key, so reading
  # one is two permissions, not one. The condition keeps this from being a
  # decrypt grant on every key in the account.
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${var.region}:${data.aws_caller_identity.current.account_id}:key/*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "read-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.read_secrets.json
}

# ── task role ───────────────────────────────────────────────────────────────
# What the application itself may do. boto3 finds these credentials on its own
# through the container credentials endpoint, which is why nothing in the image
# and nothing in the environment holds an access key: the CSV in the repo root
# has no production role at all once this is live.
resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

data "aws_iam_policy_document" "task" {
  # ECS Exec -- `aws ecs execute-command` for a shell in the running task. It
  # is how the first admin user gets created and how a migration is run, with
  # no bastion, no SSH key and no open port.
  statement {
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }

  dynamic "statement" {
    for_each = var.assets_bucket != "" ? [1] : []
    content {
      actions   = ["s3:ListBucket"]
      resources = ["arn:aws:s3:::${var.assets_bucket}"]
    }
  }

  dynamic "statement" {
    for_each = var.assets_bucket != "" ? [1] : []
    content {
      actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      resources = ["arn:aws:s3:::${var.assets_bucket}/*"]
    }
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "app"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}
