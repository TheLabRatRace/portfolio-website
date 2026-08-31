resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "this" {
  name = local.name

  # Container Insights is off on purpose: it publishes custom metrics, and
  # custom metrics are $0.30 each per month. On a stack this size the
  # monitoring would cost more than the compute.
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
}

resource "aws_ecs_task_definition" "app" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  # Graviton. Same task, about 20% cheaper per vCPU-hour than x86, and the
  # image is built for it by deploy/scripts/build_and_push.sh -- an amd64 image
  # here fails to start with an exec format error rather than running slowly.
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name      = "web"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    essential = true

    portMappings = [{ containerPort = local.container_port, protocol = "tcp" }]

    environment = [
      { name = "FLASK_ENV", value = "production" },
      # The admin blueprint is not registered in this process. /admin/login on
      # the public site is a 404 -- there is no such route here to find.
      { name = "APP_ROLE", value = "public" },
      { name = "PORT", value = tostring(local.container_port) },
      # Both of these are statements about what is in front of the container,
      # and in phase one nothing is. A Secure cookie on a plain-http site is
      # one the browser accepts and then never sends back, so the admin login
      # would appear to succeed and then bounce straight back to the form --
      # and trusting X-Forwarded-For with no proxy writing it lets any caller
      # name their own client IP.
      { name = "SESSION_COOKIE_SECURE", value = var.enable_cdn ? "1" : "" },
      { name = "TRUSTED_PROXY_HOPS", value = var.enable_cdn ? "1" : "0" },
      # The container filesystem dies with the task; stdout is what is kept.
      { name = "LOG_TO_STDOUT", value = "1" },
      # Empty until the static distribution exists, and then absolute URLs on
      # every <link> and <script>. The bytes stop passing through this task.
      { name = "STATIC_BASE_URL", value = local.static_base_url },
      { name = "S3_BUCKET", value = var.assets_bucket },
      { name = "S3_REGION", value = var.region },
      { name = "S3_PUBLIC_BASE_URL", value = var.assets_public_base_url },
    ]

    # Resolved by the ECS agent at task start and injected straight into the
    # process environment. The values are never in this file, never in the task
    # definition, and never in terraform.tfstate.
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
        "awslogs-stream-prefix" = "web"
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  name            = local.name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1

  # Shell access into the running task, for creating the first admin user and
  # running migrations. Nothing is listening for it; it is an outbound channel.
  enable_execute_command = true

  capacity_provider_strategy {
    capacity_provider = var.use_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 1
  }

  network_configuration {
    subnets = local.subnet_ids
    # The task's own public IP is how it reaches ECR, and how CloudFront
    # reaches it. Turning this off means paying for a NAT gateway, which costs
    # three times the entire rest of this stack.
    assign_public_ip = true
    security_groups  = [aws_security_group.task.id]
  }

  # Publish the task's private IP into Cloud Map, so API Gateway's VPC link has
  # a name to resolve. ECS writes the record when the task starts and removes
  # it when the task stops, which is the whole reason this is worth having --
  # the address changes on every deploy.
  #
  # Attaching this to a running service is an in-place update, and it applies
  # to tasks that start afterwards -- the task already running does not appear
  # in Cloud Map. Force a deployment after the first apply.
  dynamic "service_registries" {
    for_each = var.enable_api_gateway ? [1] : []

    content {
      registry_arn = aws_service_discovery_service.app[0].arn
      # Required by an SRV registration -- they are the host and the port it
      # publishes. ECS reads the address off the task's own ENI.
      container_name = "web"
      container_port = local.container_port
    }
  }

  # Stop the old task before starting the new one. With one task and no load
  # balancer there is no way to overlap them usefully anyway -- ECS would tear
  # the old one down the instant the new one reported healthy, well before the
  # DNS record caught up -- so overlapping would buy a doubled bill and the
  # same blip. Expect roughly a minute of downtime per deploy. That minute is
  # what a load balancer costs $16 a month to remove.
  deployment_maximum_percent         = 100
  deployment_minimum_healthy_percent = 0

  # No ignore_changes on task_definition. build_and_push.sh ships code by
  # pushing a new :latest and forcing a new deployment, which never changes
  # which revision the service points at -- so there is no drift to ignore,
  # and ignoring it would instead stop a real change here (an environment
  # variable, the CPU size) from ever reaching the service.

  depends_on = [aws_iam_role_policy.execution_secrets]
}
