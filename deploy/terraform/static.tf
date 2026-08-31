# The static bucket: CSS, JS and images, served from CloudFront instead of
# from the container.
#
# This is a different bucket from var.assets_bucket on purpose, and the reason
# is deploy/scripts/sync_static.sh. That script runs `aws s3 sync --delete`,
# because a build artifact that no longer exists in the repo should not linger
# at the edge. Pointed at a bucket that also holds uploads, --delete would
# reach content the repo has never seen and remove it. One bucket per
# lifecycle: this one is disposable and rebuilt from git, the assets bucket is
# not.

resource "aws_s3_bucket" "static" {
  count  = var.enable_static_cdn ? 1 : 0
  bucket = var.static_bucket != "" ? var.static_bucket : "${local.name}-static"
  tags   = local.tags
}

# Private, and it stays private: CloudFront reaches it with an origin access
# control, so there is no anonymous-read policy and no public URL that skips
# the cache. A bucket that is only readable through the distribution cannot be
# scraped for its own bandwidth bill.
resource "aws_s3_bucket_public_access_block" "static" {
  count  = var.enable_static_cdn ? 1 : 0
  bucket = aws_s3_bucket.static[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "static" {
  count  = var.enable_static_cdn ? 1 : 0
  bucket = aws_s3_bucket.static[0].id

  # A bad sync is otherwise unrecoverable -- the previous CSS existed only in
  # the bucket the moment the build artifact was overwritten. Versioning makes
  # `aws s3api list-object-versions` the rollback. The objects are kilobytes.
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_cloudfront_origin_access_control" "static" {
  count                             = var.enable_static_cdn ? 1 : 0
  name                              = "${local.name}-static"
  description                       = "S3 origin access for ${local.name} static assets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_iam_policy_document" "static_bucket" {
  count = var.enable_static_cdn ? 1 : 0

  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.static[0].arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    # Scoped to this one distribution, not to CloudFront in general. Without
    # the condition, any CloudFront distribution in any AWS account could be
    # pointed at this bucket and would be allowed to read it.
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.static[0].arn]
    }
  }
}

resource "aws_s3_bucket_policy" "static" {
  count  = var.enable_static_cdn ? 1 : 0
  bucket = aws_s3_bucket.static[0].id
  policy = data.aws_iam_policy_document.static_bucket[0].json
}

data "aws_cloudfront_cache_policy" "static_optimized" {
  count = var.enable_static_cdn ? 1 : 0
  name  = "Managed-CachingOptimized"
}

data "aws_cloudfront_response_headers_policy" "static_cors" {
  count = var.enable_static_cdn ? 1 : 0
  name  = "Managed-CORS-with-preflight-and-SecurityHeadersPolicy"
}

data "aws_cloudfront_cache_policy" "api_uncached" {
  count = var.enable_static_cdn && local.api_origin_enabled ? 1 : 0
  name  = "Managed-CachingDisabled"
}

# AllViewerExceptHostHeader, and the exception is the point. API Gateway routes
# on the Host header it is given; forwarding the viewer's (the CloudFront
# domain) would get every request answered with a 403 from a service that has
# never heard of that name.
data "aws_cloudfront_origin_request_policy" "api_forward" {
  count = var.enable_static_cdn && local.api_origin_enabled ? 1 : 0
  name  = "Managed-AllViewerExceptHostHeader"
}

resource "aws_cloudfront_function" "spa_router" {
  count   = var.enable_static_cdn ? 1 : 0
  name    = "${local.name}-spa-router"
  runtime = "cloudfront-js-2.0"
  comment = "Rewrite extensionless paths to /index.html so the shell can route them"
  publish = true
  code    = file("${path.module}/functions/spa_router.js")
}

resource "aws_cloudfront_distribution" "static" {
  count           = var.enable_static_cdn ? 1 : 0
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${local.name} -- static assets"
  price_class     = var.price_class

  # The bucket root holds static_site/index.html -- the shell. A request for /
  # is a request for it.
  default_root_object = "index.html"

  # No `aliases` and no viewer_certificate block beyond the default: the assets
  # are referenced by absolute URL from the app's own HTML, so the generated
  # d111111abcdef8.cloudfront.net name is a fine address for them. Adding a
  # custom domain later is an alias plus an ACM certificate in us-east-1 and
  # changes nothing else.
  origin {
    origin_id                = "static"
    domain_name              = aws_s3_bucket.static[0].bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.static[0].id
  }

  # The API, on the same origin as the shell. Without this the shell would be
  # an https page fetching a plain-http task -- blocked as mixed content -- and
  # CloudFront cannot forward to a bare IP either, so this needs a hostname.
  # Either of two things supplies one: apigw.tf's execute-api endpoint, or the
  # Route 53 record enable_cdn creates. With neither, the shell renders and
  # every fetch fails; see deploy/README.md, "Getting the shell an API".
  dynamic "origin" {
    for_each = local.api_origin_enabled ? [1] : []

    content {
      origin_id   = "task"
      domain_name = local.api_origin_domain

      custom_origin_config {
        http_port  = local.container_port
        https_port = 443
        # API Gateway speaks https and nothing else. The Route 53 record points
        # at the task, which has no certificate and terminates plaintext on its
        # container port.
        origin_protocol_policy   = var.enable_api_gateway ? "https-only" : "http-only"
        origin_ssl_protocols     = ["TLSv1.2"]
        origin_read_timeout      = 30
        origin_keepalive_timeout = 5
      }
    }
  }

  dynamic "ordered_cache_behavior" {
    for_each = local.api_origin_enabled ? [1] : []

    content {
      path_pattern           = "/api/*"
      target_origin_id       = "task"
      viewer_protocol_policy = "redirect-to-https"
      allowed_methods        = ["GET", "HEAD", "OPTIONS"]
      cached_methods         = ["GET", "HEAD"]
      compress               = true

      # Uncached. The responses are small JSON and the content changes when an
      # admin says so, not on a schedule -- an edge cache here would mean the
      # admin publishes a post and cannot see it. AllViewerExceptHostHeader
      # forwards the query string, which is what carries ?page and ?q.
      cache_policy_id          = data.aws_cloudfront_cache_policy.api_uncached[0].id
      origin_request_policy_id = data.aws_cloudfront_origin_request_policy.api_forward[0].id
    }
  }

  default_cache_behavior {
    target_origin_id       = "static"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    compress               = true

    cache_policy_id            = data.aws_cloudfront_cache_policy.static_optimized[0].id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.static_cors[0].id

    # Turns /projects/foo into a request for index.html, so the shell's router
    # gets the path. Attached here and not to /api/*, which is the whole point
    # -- see the function for why the obvious custom_error_response is wrong.
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_router[0].arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = local.tags
}
