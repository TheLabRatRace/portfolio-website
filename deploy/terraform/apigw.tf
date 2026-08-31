# An https front door for the API, without owning a domain.
#
# The static shell is served from CloudFront over https, so its fetches have to
# be https too -- a browser will not let an https page call a plain-http
# backend, and no amount of CORS configuration changes that. CloudFront can
# forward /api/* to a custom origin, but a custom origin is a hostname, and the
# Fargate task has only a public IP that changes on every deploy.
#
# The domain-shaped answer is dns.tf: a Route 53 record tracking the task, an
# ACM certificate, a CloudFront alias. It needs a registered domain. This file
# is the answer that does not: API Gateway hands out
# <api-id>.execute-api.<region>.amazonaws.com, already valid for https, already
# a name CloudFront will accept as an origin. The requests cost about a dollar
# per million and the VPC link itself is free on HTTP APIs.
#
# Reaching the task from API Gateway needs a name too, which is what Cloud Map
# provides: ECS registers each task's private IP as an A record in a private
# zone as the task starts, and removes it as the task stops. The VPC link is
# what lets a managed service outside the VPC resolve and reach that record.

resource "aws_service_discovery_private_dns_namespace" "internal" {
  count       = var.enable_api_gateway ? 1 : 0
  name        = "${local.name}.internal"
  description = "Private DNS for ${local.name} tasks, resolvable inside the VPC only"
  vpc         = local.vpc_id
  tags        = local.tags
}

resource "aws_service_discovery_service" "app" {
  count = var.enable_api_gateway ? 1 : 0
  name  = "app"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.internal[0].id

    # SRV, not A, and the port is the whole reason. An A record publishes the
    # task's private IP and nothing else, so API Gateway resolves the name and
    # then connects to port 80 -- the container binds 5002, and every request
    # comes back a bare 500 with no detail anywhere. SRV carries host and port
    # together, which is the only shape of record that describes this backend.
    dns_records {
      type = "SRV"
      ttl  = 10
    }

    routing_policy = "MULTIVALUE"
  }

  # ECS owns the health of the registration: it deregisters the instance when
  # it stops the task. Cloud Map's own health checking is for the public DNS
  # namespaces and would only add a second opinion that arrives later.
  health_check_custom_config {
    failure_threshold = 1
  }

  tags = local.tags
}

# The link's own group. API Gateway sends from these addresses, and this is the
# group the task's ingress rule names -- so the opening on 5002 is "whatever is
# behind the VPC link", not a CIDR that would have to be maintained.
resource "aws_security_group" "vpc_link" {
  count       = var.enable_api_gateway ? 1 : 0
  name        = "${local.name}-vpc-link"
  description = "API Gateway VPC link: reaches the task on its container port"
  vpc_id      = local.vpc_id
  tags        = { Name = "${local.name}-vpc-link" }
}

resource "aws_vpc_security_group_egress_rule" "vpc_link" {
  count             = var.enable_api_gateway ? 1 : 0
  security_group_id = aws_security_group.vpc_link[0].id
  description       = "To the task"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "from_vpc_link" {
  count                        = var.enable_api_gateway ? 1 : 0
  security_group_id            = aws_security_group.task.id
  description                  = "HTTP from the API Gateway VPC link"
  referenced_security_group_id = aws_security_group.vpc_link[0].id
  ip_protocol                  = "tcp"
  from_port                    = local.container_port
  to_port                      = local.container_port
}

resource "aws_apigatewayv2_vpc_link" "this" {
  count              = var.enable_api_gateway ? 1 : 0
  name               = local.name
  security_group_ids = [aws_security_group.vpc_link[0].id]
  subnet_ids         = local.subnet_ids
  tags               = local.tags
}

# An HTTP API, not a REST API. The REST flavour costs three and a half times as
# much per request, and every feature that buys -- request validation, usage
# plans, API keys -- is a feature this API does not use.
resource "aws_apigatewayv2_api" "public" {
  count         = var.enable_api_gateway ? 1 : 0
  name          = "${local.name}-api"
  description   = "https front door for ${local.name}'s JSON API"
  protocol_type = "HTTP"
  tags          = local.tags
}

resource "aws_apigatewayv2_integration" "app" {
  count                  = var.enable_api_gateway ? 1 : 0
  api_id                 = aws_apigatewayv2_api.public[0].id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  connection_type        = "VPC_LINK"
  connection_id          = aws_apigatewayv2_vpc_link.this[0].id
  integration_uri        = aws_service_discovery_service.app[0].arn
  payload_format_version = "1.0"

  # Rebuild the path the client asked for. The route strips /api/ into the
  # proxy variable, and without this the backend would be asked for whatever
  # API Gateway decided to forward; Flask routes on the exact path, so it is
  # worth stating rather than inheriting.
  request_parameters = {
    "overwrite:path" = "/api/$request.path.proxy"
  }

  timeout_milliseconds = 30000
}

resource "aws_apigatewayv2_route" "app" {
  count     = var.enable_api_gateway ? 1 : 0
  api_id    = aws_apigatewayv2_api.public[0].id
  route_key = "ANY /api/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.app[0].id}"
}

# $default, so the invoke URL has no stage segment in it. A named stage would
# put /prod in front of every path, and CloudFront would then have to rewrite
# /api/v1/tags into /prod/api/v1/tags with a function -- machinery bought for
# nothing, since there is one stage and there will only ever be one.
resource "aws_apigatewayv2_stage" "default" {
  count       = var.enable_api_gateway ? 1 : 0
  api_id      = aws_apigatewayv2_api.public[0].id
  name        = "$default"
  auto_deploy = true
  tags        = local.tags
}
