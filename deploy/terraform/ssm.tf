# SSM Parameter Store, not Secrets Manager. The two do the same job here --
# ECS reads either one into the container's environment and neither value ever
# lands in the task definition -- but a Standard SecureString parameter is
# free and a Secrets Manager secret is $0.40 a month, which on a $12 stack is
# not a rounding error. Rotation is what Secrets Manager sells beyond this, and
# nothing here rotates on a schedule.
#
# The values are deliberately NOT in Terraform. Putting them here would write
# the database password into terraform.tfstate in plaintext. deploy/scripts/
# put_secrets.sh pushes them with the CLI; this only declares that they exist
# and reads back the ARNs the task definition needs.
locals {
  secret_names = {
    secret_key   = "/${local.name}/${var.region}/SECRET_KEY"
    database_url = "/${local.name}/${var.region}/DATABASE_URL"
  }
}

data "aws_ssm_parameter" "secret_key" {
  name            = local.secret_names.secret_key
  with_decryption = false
}

data "aws_ssm_parameter" "database_url" {
  name            = local.secret_names.database_url
  with_decryption = false
}
