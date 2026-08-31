#!/usr/bin/env bash
#
# Push the static site to its bucket and invalidate the edge cache.
#
# Two halves live in one bucket, and the split is deliberate:
#
#   s3://bucket/static/   app/static -- the CSS, JS and images both the
#                         containers and the shell reference
#   s3://bucket/          static_site -- the shell itself: index.html and the
#                         router that fetches everything else from the API
#
# Neither --delete may reach the other half, which is why the first two passes
# are prefixed and the third excludes that prefix.
#
# Run this after every change to CSS, JS or images, and before the deploy that
# ships the HTML referencing them -- assets first, then the page that asks for
# them, so no visitor is ever sent to a file that has not been uploaded yet.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TF_DIR="${TF_DIR:-$ROOT/deploy/terraform}"
STATIC_DIR="$ROOT/app/static"
SHELL_DIR="$ROOT/static_site"

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

printf 'Syncing to s3://%s\n' "$BUCKET"

# Two passes, because the two kinds of file have different cache lifetimes.
#
# CSS and JS are referenced with a ?v=<digest> of their contents, so a changed
# file is a URL the browser has never seen and a year is safe. Note that the
# digest does NOT protect CloudFront: the managed CachingOptimized policy does
# not put query strings in its cache key, so the edge would keep serving the
# old bytes. The invalidation below is what handles that half.
aws s3 sync "$STATIC_DIR/" "s3://$BUCKET/static/" \
  --exclude "*" --include "css/*" --include "js/*" \
  --cache-control "public, max-age=31536000" \
  --delete --only-show-errors
printf '  css, js\n'

# Images carry no digest, so a year would be wrong: an invalidation clears the
# edge but never reaches a browser that already has the file. A week is short
# enough that a replaced image corrects itself for returning visitors and long
# enough that it is still cached for everyone reading the site today.
aws s3 sync "$STATIC_DIR/" "s3://$BUCKET/static/" \
  --exclude "css/*" --exclude "js/*" \
  --cache-control "public, max-age=604800" \
  --delete --only-show-errors
printf '  images\n'

# The shell: index.html plus the router, at the bucket root.
#
# Its three <script>/<link> tags carry ?v=__ASSET_V__, substituted here with a
# digest over the files that token stands for. One token for all three because
# they change together -- the router and the stylesheet are one deployment --
# and a single token is one substitution rather than three.
if [[ -d "$SHELL_DIR" ]]; then
  VERSION="$(cat "$SHELL_DIR/app.js" "$SHELL_DIR/config.js" \
    "$STATIC_DIR/css/style.min.css" 2>/dev/null | shasum -a 256 | cut -c1-8)"

  # Where the shell sends its fetches. Same-origin by default, which is what
  # the /api/* cache behaviour in front of the task makes true; override it
  # when the API lives on a hostname of its own.
  API_BASE="${API_BASE:-/api/v1}"

  BUILD="$(mktemp -d)"
  trap 'rm -rf "$BUILD"' EXIT
  cp -R "$SHELL_DIR/." "$BUILD/"
  # LC_ALL=C: sed on macOS rejects bytes it cannot decode in the current
  # locale, and one em dash in the copy is enough to stop the build.
  LC_ALL=C find "$BUILD" -type f -name '*.html' -o -type f -name '*.js' \
    | while read -r f; do
        LC_ALL=C sed -i '' -e "s|__ASSET_V__|$VERSION|g" \
          -e "s|__API_BASE__|$API_BASE|g" "$f"
      done

  # No --delete without the exclude: the shell's sync target is the bucket
  # root, and an unqualified --delete would take app/static with it.
  #
  # index.html is not versioned -- it is the file that carries the version --
  # so it gets no-cache and is revalidated on every visit. Everything else
  # here is referenced with ?v= and can be held.
  aws s3 sync "$BUILD/" "s3://$BUCKET/" \
    --exclude "static/*" --exclude "index.html" \
    --cache-control "public, max-age=31536000" \
    --delete --only-show-errors
  aws s3 cp "$BUILD/index.html" "s3://$BUCKET/index.html" \
    --cache-control "no-cache" --content-type "text/html; charset=utf-8" \
    --only-show-errors
  printf '  shell (v=%s, api=%s)\n' "$VERSION" "$API_BASE"
fi

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
