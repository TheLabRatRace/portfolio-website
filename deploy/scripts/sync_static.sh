#!/usr/bin/env bash
#
# Push app/static to the static bucket and invalidate the edge cache.
#
# Run this after every change to CSS, JS or images, and before the deploy that
# ships the HTML referencing them -- assets first, then the page that asks for
# them, so no visitor is ever sent to a file that has not been uploaded yet.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TF_DIR="${TF_DIR:-$ROOT/deploy/terraform}"
STATIC_DIR="$ROOT/app/static"

die() { printf '\nerror: %s\n' "$1" >&2; exit 1; }

[[ -d "$STATIC_DIR" ]] || die "no static directory at $STATIC_DIR"

BUCKET="${STATIC_BUCKET:-$(terraform -chdir="$TF_DIR" output -raw static_bucket 2>/dev/null || true)}"
[[ -n "$BUCKET" && "$BUCKET" != "null" ]] \
  || die "no static bucket. Run terraform apply with enable_static_cdn = true,
       or set STATIC_BUCKET=... to sync somewhere else."

DIST="${STATIC_DISTRIBUTION_ID:-$(terraform -chdir="$TF_DIR" output -raw static_distribution_id 2>/dev/null || true)}"

# The minified stylesheet is a build artifact, and the app silently falls back
# to the unminified one when it is stale. That fallback is invisible here --
# the sync would happily upload a month-old style.min.css -- so rebuild first.
if [[ -f "$ROOT/tools/minify_css.py" ]]; then
  python3 "$ROOT/tools/minify_css.py" >/dev/null && printf 'Rebuilt style.min.css\n'
fi

printf 'Syncing %s -> s3://%s\n' "${STATIC_DIR#"$ROOT"/}" "$BUCKET"

# Two passes, because the two kinds of file have different cache lifetimes.
#
# CSS and JS are referenced with a ?v=<digest> of their contents, so a changed
# file is a URL the browser has never seen and a year is safe. Note that the
# digest does NOT protect CloudFront: the managed CachingOptimized policy does
# not put query strings in its cache key, so the edge would keep serving the
# old bytes. The invalidation below is what handles that half.
aws s3 sync "$STATIC_DIR/" "s3://$BUCKET/" \
  --exclude "*" --include "css/*" --include "js/*" \
  --cache-control "public, max-age=31536000" \
  --delete --only-show-errors
printf '  css, js\n'

# Images carry no digest, so a year would be wrong: an invalidation clears the
# edge but never reaches a browser that already has the file. A week is short
# enough that a replaced image corrects itself for returning visitors and long
# enough that it is still cached for everyone reading the site today.
aws s3 sync "$STATIC_DIR/" "s3://$BUCKET/" \
  --exclude "css/*" --exclude "js/*" \
  --cache-control "public, max-age=604800" \
  --delete --only-show-errors
printf '  images\n'

if [[ -n "$DIST" && "$DIST" != "null" ]]; then
  ID="$(aws cloudfront create-invalidation \
    --distribution-id "$DIST" --paths "/*" \
    --query "Invalidation.Id" --output text)"
  printf 'Invalidation %s created (usually under a minute)\n' "$ID"
else
  printf 'No distribution id -- skipping invalidation.\n'
fi

cat <<'EOF'

Done. The containers already know the URL: STATIC_BASE_URL comes from the
task definition, so nothing needs redeploying unless a template changed.

The first 1,000 invalidation paths each month are free; "/*" counts as one.
EOF
