# The admin application: the same image as the public site, run with
# APP_ROLE=admin so it registers the admin blueprint and nothing else.
#
# It is a separate ECS service, on its own security group, scaled to zero. Two
# things follow from that, and both are the point:
#
#   * The public container has no /admin routes at all. Not hidden behind a
#     login -- absent from the URL map, because that process never registered
#     the blueprint. There is no session check to get wrong.
#   * The admin container is not running. Most of the time the login form does
#     not exist anywhere on the internet. Bringing it up is a deliberate act
#     that takes about ninety seconds, and putting it away is one command.
#
# Scaled to zero it costs nothing but the log storage. Running it costs about
# a cent an hour.

resource "aws_ecs_task_definition" "admin" {
  family                   = "${local.name}-admin"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.admin_task_cpu
  memory                   = var.admin_task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name      = "admin"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    essential = true

    portMappings = [{ containerPort = local.container_port, protocol = "tcp" }]

    environment = [
      { name = "FLASK_ENV", value = "production" },
      { name = "APP_ROLE", value = "admin" },
      { name = "PORT", value = tostring(local.container_port) },
      # Nothing is in front of this task -- CloudFront fronts the public site
      # only -- so both of these stay off however the public side is set up. A
      # Secure cookie over plain http is accepted by the browser and then never
      # sent back, which reads as a login that succeeds and instantly forgets.
      { name = "SESSION_COOKIE_SECURE", value = "" },
      { name = "TRUSTED_PROXY_HOPS", value = "0" },
      { name = "LOG_TO_STDOUT", value = "1" },
      { name = "PUBLIC_SITE_URL", value = local.public_site_url },
      { name = "S3_BUCKET", value = var.assets_bucket },
      { name = "S3_REGION", value = var.region },
      { name = "S3_PUBLIC_BASE_URL", value = var.assets_public_base_url },
    ]

    secrets = [
      { name = "SECRET_KEY", valueFrom = data.aws_ssm_parameter.secret_key.arn },
      { name = "DATABASE_URL", valueFrom = data.aws_ssm_parameter.database_url.arn },
    ]

    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:${local.container_port}/healthz', timeout=4).status == 200 else 1)\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 15
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "admin"
      }
    }
  }])
}

resource "aws_security_group" "admin" {
  name        = "${local.name}-admin"
  description = "Admin Fargate task: HTTP in from named addresses only"
  vpc_id      = local.vpc_id
  tags        = { Name = "${local.name}-admin" }
}

resource "aws_vpc_security_group_ingress_rule" "admin_direct" {
  for_each = toset(local.admin_cidrs)

  security_group_id = aws_security_group.admin.id
  description       = "Direct HTTP to the admin task"
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = local.container_port
  to_port           = local.container_port
}

resource "aws_vpc_security_group_egress_rule" "admin_all" {
  security_group_id = aws_security_group.admin.id
  description       = "ECR, CloudWatch Logs, S3, RDS"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# Its own opening on the database, so the admin service can be revoked without
# touching the public site's access -- and so the audit answer to "what can
# write to this database" names two groups rather than one shared one.
resource "aws_vpc_security_group_ingress_rule" "rds_from_admin" {
  count                        = var.rds_security_group_id != "" ? 1 : 0
  security_group_id            = var.rds_security_group_id
  description                  = "Postgres from the ${local.name} admin task"
  referenced_security_group_id = aws_security_group.admin.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_ecs_service" "admin" {
  name            = "${local.name}-admin"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.admin.arn
  desired_count   = 0

  # For `aws ecs execute-command` into the admin task: create-admin, migrations,
  # anything that wants a shell next to the database.
  enable_execute_command = true

  capacity_provider_strategy {
    capacity_provider = var.use_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 1
  }

  network_configuration {
    subnets          = local.subnet_ids
    assign_public_ip = true
    security_groups  = [aws_security_group.admin.id]
  }

  deployment_maximum_percent         = 100
  deployment_minimum_healthy_percent = 0

  lifecycle {
    # desired_count is operational state here, not configuration. admin_up.sh
    # sets it to 1 and admin_down.sh sets it back to 0; without this, the next
    # `terraform apply` would helpfully shut the admin down mid-edit.
    ignore_changes = [desired_count]
  }

  depends_on = [aws_iam_role_policy.execution_secrets]
}
