# Security

## Reporting a vulnerability

Do not open a public issue. Issues are readable by anyone with access to the
repository and there is no way to un-publish one.

Instead, either

* use **private vulnerability reporting** — the *Report a vulnerability* button
  under the repository's Security tab, which opens a draft advisory only the
  maintainers can read — or
* email the address on the site's contact page.

Please include what you did, what happened, and what you expected. A proof of
concept helps; a working exploit is not required. Expect a first reply within a
week — this is a personal project maintained by one person, not a funded
programme.

## Scope

In scope: this application's code and its container image. Out of scope: the
hosting provider, the domain registrar, denial of service, and anything that
requires already having a shell on the host.

## What must never enter this repository

`.gitignore` blocks all of the following by pattern, and the pipeline's
`secret_detection` job scans every diff for them anyway. If one is ever
committed, treat it as disclosed even after the commit is removed — history is
recoverable, and mirrors, forks and CI caches keep their own copies.

* `.env` and any `.env.*` other than `.env.example`
* private keys and certificates (`*.pem`, `*.key`, `*.p12`, `id_rsa*`, …)
* `agent-guidance/` — the sibling V1 checkout keeps plaintext credentials there
* anything named like `creds`, `credentials`, `secrets`

`.env.example` is the one file that documents these variables. It holds
placeholders exclusively and is the right place to add a new setting's name.

## If a credential is committed anyway

1. **Rotate it first.** Removing the commit does not un-leak the value; the
   value is what has to change.
2. Then rewrite history (`git filter-repo`, or a fresh branch) and force-push.
3. Delete any pipeline artifacts, caches, and container images built from the
   affected commits.
4. Ask GitHub Support to purge the cached view of the affected commits if the
   repository is public — a force-push hides them, but they stay reachable by
   SHA until support clears them.

## How the pipeline handles credentials

No secret is written into `.github/workflows/ci.yml`.

* The CI Postgres service runs with `POSTGRES_HOST_AUTH_METHOD=trust` on the
  job's private network, so it has no password to leak.
* `SECRET_KEY` is generated inside the job with `secrets.token_hex` and dies
  with the job.
* Registry access uses the automatic `GITHUB_TOKEN`, scoped to this repository
  and expired when the job ends. `docker/login-action` passes it on stdin, so it
  never reaches the job log or the runner's process list.
* `permissions:` defaults to `contents: read` for the whole workflow; only the
  image job widens it, and only to `packages: write`.
* Everything a real deployment needs lives in **Settings ▸ Secrets and variables
  ▸ Actions**, and is referenced by name only.

## Application security notes

* The container runs as an unprivileged user (uid 10001), not root.
* `SECRET_KEY` has an insecure default (`dev-secret-change-in-production`) so a
  fresh checkout starts. Any deployment must override it.
* `DEBUG` is off in `ProductionConfig`, and the compose file's `DEV_RELOAD=1` is
  local-only — the image's own defaults leave it off.
* Templates rely on Jinja's autoescaping. Anything rendered with `|safe` is a
  deliberate exception and deserves a second look in review.

## The admin area

`/admin` is the site's only authenticated surface and therefore the only place
where a bug costs more than a broken page. What it relies on:

* **The gate is a blueprint-wide `before_request`, not a per-view decorator.**
  A new admin route is protected the moment it exists; exposing one means
  adding its endpoint to `PUBLIC_ENDPOINTS`, which is a visible edit in a
  diff. A forgotten decorator cannot silently publish a route.
* **Authentication and authorisation are separate checks.** A signed-in user
  without `is_admin` receives a 403. Being a user is not being an admin.
* **Passwords are stored as Werkzeug scrypt hashes** (`scrypt:32768:8:1`,
  per-user salt) and never logged. There
  is no seed account and no default password: the first admin is created by
  `flask create-admin`, which prompts on a TTY and refuses to run without one,
  so the password never becomes a shell argument, a history entry, or a line in
  `ps`.
* **A failed login says only "Wrong username or password."** Distinguishing the
  two cases turns the form into a username oracle. Failures are logged with the
  attempted username and the source address; successes are logged too.
* **`?next=` is refused unless it is a local path** — no scheme, no host, and
  not `//host`. An open redirect here would make the real login page, on the
  real domain, with a real certificate, into a credible phishing link.
* **The session cookie is HttpOnly and SameSite=Lax**, and `SESSION_COOKIE_SECURE`
  must be set wherever the site is served over TLS. It is off by default only
  because local development is plain HTTP, where a Secure cookie is a cookie
  the browser silently refuses to send. Flask-Login runs with
  `session_protection = "strong"`.
* **CSRF protection is global** (`CSRFProtect`), so every state-changing POST
  needs a token; SameSite=Lax is the first lock and the token is the second.
  `TestingConfig` disables it so tests can post forms, and one test turns it
  back on to prove a tokenless POST is rejected.
* **Uploads are constrained by extension and size** (`ALLOWED_IMAGE_EXTENSIONS`,
  `MAX_CONTENT_LENGTH` of 16 MB) and land under `static/images/uploads/`. An
  uploaded file is served as a static asset, so an SVG is worth remembering:
  it can carry script and is same-origin. Prefer raster formats for anything
  supplied by someone other than the site owner.

Anything reachable without signing in — the public pages, and `/search` — is
read-only and filters on `published`, so a draft cannot leak its title through
the search box.
