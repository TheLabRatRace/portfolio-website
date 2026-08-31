# ── certificate ─────────────────────────────────────────────────────────────
resource "aws_acm_certificate" "site" {
  count    = var.enable_cdn ? 1 : 0
  provider = aws.us_east_1

  domain_name               = local.site_domain
  subject_alternative_names = distinct([local.site_domain, "www.${var.domain_name}"])
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  # Iterating the resource list rather than indexing it: with count = 0 this
  # is an empty list, an empty map, and no instances -- where site[0] would be
  # an error before Terraform ever got to the condition.
  for_each = {
    for option in flatten([for cert in aws_acm_certificate.site : cert.domain_validation_options]) :
    option.domain_name => option
  }

  zone_id         = data.aws_route53_zone.this[0].zone_id
  name            = each.value.resource_record_name
  type            = each.value.resource_record_type
  records         = [each.value.resource_record_value]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "site" {
  count    = var.enable_cdn ? 1 : 0
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.site[0].arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# ── policies ────────────────────────────────────────────────────────────────
# Looked up by name rather than pasted as UUIDs: the managed policy IDs are
# opaque and a wrong one is a page that half-works.
data "aws_cloudfront_cache_policy" "disabled" {
  count = var.enable_cdn ? 1 : 0
  name  = "Managed-CachingDisabled"
}

data "aws_cloudfront_cache_policy" "optimized" {
  count = var.enable_cdn ? 1 : 0
  name  = "Managed-CachingOptimized"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  count = var.enable_cdn ? 1 : 0
  name  = "Managed-AllViewer"
}

data "aws_cloudfront_response_headers_policy" "security" {
  count = var.enable_cdn ? 1 : 0
  name  = "Managed-SecurityHeadersPolicy"
}

# ── distribution ────────────────────────────────────────────────────────────
resource "aws_cloudfront_distribution" "site" {
  count           = var.enable_cdn ? 1 : 0
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${local.name} -- ${local.site_domain}"
  aliases         = distinct([local.site_domain, "www.${var.domain_name}"])
  price_class     = var.price_class

  origin {
    origin_id   = "task"
    domain_name = aws_route53_record.origin[0].fqdn

    custom_origin_config {
      http_port  = local.container_port
      https_port = 443

      # http-only, and this is the one real cost of not running a load
      # balancer. CloudFront cannot speak TLS to this origin: a certificate for
      # the origin hostname would have to live inside the container, ACM will
      # not export one, and CloudFront rejects a self-signed origin. So the hop
      # from the edge to the task is plaintext across the public internet.
      #
      # What contains it: the task's security group accepts traffic only from
      # CloudFront's published origin-facing ranges, so the origin is not
      # reachable directly and never appears in a port scan. What remains is an
      # on-path attacker between a CloudFront edge and us-east-2 -- a
      # network-level adversary, not a passerby.
      #
      # If that is not an acceptable residual for the admin login, the fix is
      # an Application Load Balancer with an ACM certificate in front of the
      # task, which ends the plaintext hop and costs about $16 a month. See
      # deploy/README.md, "The plaintext origin hop".
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]

      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

  # Dynamic HTML: sessions, CSRF tokens, admin pages. Nothing here is cacheable
  # and caching it would serve one visitor's logged-in page to the next one.
  # AllViewer forwards the viewer's Host header through, which is what lets
  # Flask generate correct absolute URLs.
  default_cache_behavior {
    target_origin_id       = "task"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled[0].id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer[0].id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security[0].id
  }

  # CSS, JS and images. This is most of the byte volume and all of the requests
  # that a 0.25 vCPU task should not be spending its time on -- served from the
  # edge, the origin sees each file roughly once.
  ordered_cache_behavior {
    path_pattern           = "/static/*"
    target_origin_id       = "task"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized[0].id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security[0].id
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.site[0].certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
}
