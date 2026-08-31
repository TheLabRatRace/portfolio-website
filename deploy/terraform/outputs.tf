output "site_url" {
  description = "The address the site answers on once DNS has propagated."
  value       = "https://${local.site_domain}"
}

output "cloudfront_domain" {
  description = "Distribution domain. Useful for testing before the DNS alias resolves."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "origin_record" {
  description = "Internal hostname tracking the running task. Resolve it to see which IP is live."
  value       = aws_route53_record.origin.fqdn
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
