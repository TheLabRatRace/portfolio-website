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

resource "aws_cloudfront_distribution" "static" {
  count           = var.enable_static_cdn ? 1 : 0
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${local.name} -- static assets"
  price_class     = var.price_class

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

  default_cache_behavior {
    target_origin_id       = "static"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    compress               = true

    cache_policy_id            = data.aws_cloudfront_cache_policy.static_optimized[0].id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.static_cors[0].id
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
