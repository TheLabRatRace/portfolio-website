#!/usr/bin/env bash
#
# Push SECRET_KEY and DATABASE_URL into SSM Parameter Store as SecureStrings.
#
# Run this BEFORE the first `terraform apply`: the configuration reads these
# parameters to get their ARNs, and plan fails if they are not there yet.
#
# No value is ever printed, echoed, or written to a file. The only place they
# end up is Parameter Store, encrypted, and the task's process environment.
set -euo pipefail

PROJECT="${PROJECT:-portfolio}"
REGION="${AWS_REGION:-us-east-2}"
ENV_FILE="${ENV_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.env}"

die() { printf '\nerror: %s\n' "$1" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || die "no env file at $ENV_FILE (override with ENV_FILE=...)"

# Read one key out of the env file without sourcing it.
#
# `source` is the obvious way to do this and it is wrong here. Docker Compose
# parses .env literally, so a database URL is written unquoted -- and the query
# string that makes the connection safe, ?sslmode=verify-full&sslrootcert=...,
# contains an ampersand. Sourcing that backgrounds the assignment at the & and
# silently leaves the variable unset, which reads as "the key is missing" when
# it is right there in the file. Parsing sidesteps that, and also stops this
# script from executing whatever else the file happens to contain.
env_value() {
  local key="$1" line
  line="$(grep -m1 -E "^[[:space:]]*(export[[:space:]]+)?${key}=" "$ENV_FILE" || true)"
  [[ -n "$line" ]] || return 0
  line="${line#*=}"
  # Strip one layer of surrounding quotes if present; Compose accepts both.
  if [[ "$line" == \"*\" && ${#line} -ge 2 ]]; then
    line="${line:1:${#line}-2}"
  elif [[ "$line" == \'*\' && ${#line} -ge 2 ]]; then
    line="${line:1:${#line}-2}"
  fi
  printf '%s' "$line"
}

SECRET_KEY="$(env_value SECRET_KEY)"
[[ -n "$SECRET_KEY" ]] || die "SECRET_KEY is not set in $ENV_FILE"

DB_URL="$(env_value RDS_DATABASE_URL)"
[[ -n "$DB_URL" ]] || DB_URL="$(env_value DATABASE_URL)"
[[ -n "$DB_URL" ]] || die "neither RDS_DATABASE_URL nor DATABASE_URL is set in $ENV_FILE"

# The app refuses to boot in production on a remote database without
# verify-full and a trust store, which is correct -- but on ECS that refusal is
# a task that crash-loops with the reason buried in CloudWatch. Catch it here,
# where the message is in front of you.
[[ "$DB_URL" == *"sslmode=verify-full"* ]] \
  || die "DATABASE_URL has no sslmode=verify-full. The app will refuse to start."
[[ "$DB_URL" == *"sslrootcert=/app/certs/global-bundle.pem"* ]] \
  || die "DATABASE_URL must use sslrootcert=/app/certs/global-bundle.pem -- that is
       where the bundle lives inside the image. A host path resolves to nothing
       in the container and the app will refuse to start."

# 32 characters is not a policy, it is the shortest key that is obviously not a
# placeholder. The app has its own list of known-bad values and refuses those.
[[ ${#SECRET_KEY} -ge 32 ]] || die "SECRET_KEY is only ${#SECRET_KEY} characters. Generate a real one:
       python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""

put() {
  aws ssm put-parameter \
    --region "$REGION" \
    --name "$1" \
    --value "$2" \
    --type SecureString \
    --overwrite \
    --output text --query Version >/dev/null
  printf '  %-40s stored\n' "$1"
}

printf 'Writing SecureStrings to %s in %s\n' "$PROJECT" "$REGION"
put "/${PROJECT}/${REGION}/SECRET_KEY"   "$SECRET_KEY"
put "/${PROJECT}/${REGION}/DATABASE_URL" "$DB_URL"

cat <<'EOF'

Done. Values are encrypted under the account's default SSM key and are readable
only by the ECS execution role.

To rotate one later, re-run this script and then force a new deployment --
secrets are resolved at task start, so a running task keeps the old value.
EOF
