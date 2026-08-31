resource "aws_ecr_repository" "app" {
  name                 = local.name
  image_tag_mutability = "MUTABLE"

  # Every push is scanned for known CVEs in the base image and the wheels, at
  # no charge on the basic tier.
  image_scanning_configuration {
    scan_on_push = true
  }
}

# Without this, every build's image is kept forever at $0.10/GB/month and the
# repository quietly becomes the second largest line on the bill.
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images; the rest are rollback targets nobody will use."
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}
