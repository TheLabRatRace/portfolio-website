# Phase one has no stable address to output. A Fargate task cannot hold an
# Elastic IP, so its public IP is assigned at task start and is a different
# address after every deploy -- something Terraform cannot know at plan time and
# has no reason to re-read afterwards. deploy/scripts/task_ip.sh asks ECS for
# the address of whichever task is running now, which is the only correct
# answer to "where is the site".
output "site_url" {
  description = "The address the site answers on. Empty until enable_cdn = true -- until then use deploy/scripts/task_ip.sh."
  value       = var.enable_cdn ? "https://${local.site_domain}" : ""
}

output "cloudfront_domain" {
  description = "Distribution domain. Useful for testing before the DNS alias resolves."
  value       = one(aws_cloudfront_distribution.site[*].domain_name)
}

output "origin_record" {
  description = "Internal hostname tracking the running task. Resolve it to see which IP is live."
  value       = one(aws_route53_record.origin[*].fqdn)
}

output "container_port" {
  description = "The port the task listens on. It is in the phase-one URL because the container runs unprivileged and cannot bind 80."
  value       = local.container_port
}

output "ecr_repository_url" {
  description = "Push target for deploy/scripts/build_and_push.sh."
  value       = aws_ecr_repository.app.repository_url
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "service_name" {
  value = aws_ecs_service.app.name
}

output "task_security_group_id" {
  description = "Allow this group inbound on 5432 in the RDS security group, then set the instance to not publicly accessible."
  value       = aws_security_group.task.id
}

output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "region" {
  value = var.region
}
