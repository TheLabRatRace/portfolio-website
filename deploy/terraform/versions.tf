terraform {
  required_version = ">= 1.9"

  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.60" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

# CloudFront reads its certificate out of us-east-1 and nowhere else, whatever
# region the site itself runs in. This alias exists only to issue that one cert.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = local.tags
  }
}
