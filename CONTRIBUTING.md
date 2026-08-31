# Contributing

## Getting a stack up

    cp .env.example .env             # fill in SECRET_KEY and RDS_DATABASE_URL
    docker compose up -d --build     # http://localhost:5003

**That connects to AWS RDS.** It is the real database the site serves from,
so a stack brought up this way is not a sandbox. For one that is:

    docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

That runs against the throwaway `db` container on its own volume. Break it
freely; `tools/seed_stress.py --reset` puts the content back. V2 remains
isolated from V1 either way — its own compose project, volume and port.

To reach `/admin` you need an account, and there is no seed one:

    docker compose exec -it web flask create-admin

## Before you open a pull request

    docker compose exec -T web python -m pytest -q
    ruff check app config.py run.py tools tests

The pipeline runs both plus a template compile check, a dependency audit, a
secret scan, and a Docker build with a smoke test. Running the first two
locally catches almost everything before a runner is involved.

The tests run against real Postgres — search needs it — but never against
RDS. They read `TEST_DATABASE_URL`, which compose pins to the local `db`
container, and `create_app("testing")` refuses to start against a remote
host. So `docker compose exec web pytest` is safe from either stack; you do
not need the local override to run it.

Within that database, **check that a test run leaves the row counts
unchanged.** Every test that writes takes the `db_session` fixture, which
rolls its transaction back. A test that writes without it will pass and
quietly seed your data; that has already happened once, and the counts are
the only thing that catches it.

## House rules

**Prevent fragmentation.** This codebase moves fast, which is exactly why a
second way of doing an existing thing costs more than it saves. Before adding a
component, a helper or a CSS block, look for the one that already exists and
extend it.

**Comments explain why, not what.** The existing code is dense with reasoning —
why `_ordered` needs a total ordering, why the overlays get hoisted onto
`<body>`, why `variants.json` is read once at startup. Match that. A comment
that restates the line below it is noise; a comment recording the measurement
or the bug that forced a decision saves the next person an afternoon.

**Measure before you optimise.** `tools/` holds the harnesses used to settle
previous arguments — `ab_loaders.py`, `ab_pagination.py`, `tiecheck.py`,
`viewport_audit.js`. Add to them rather than asserting a number.

**A new admin route is protected unless you say otherwise.** The gate is a
blueprint-wide `before_request`, so adding a view is enough. Making one public
means naming its endpoint in `PUBLIC_ENDPOINTS` — do that only on purpose, and
expect it to be the part of the diff that gets read closely.

**Keep CSS breakpoints in step with the `sizes` attributes.** The gallery card
and detail panel hard-code the slot widths the CSS gives them. Change one and
the other is wrong, silently — the page still renders, it just downloads the
wrong file.

## Secrets

Never commit one. `.gitignore` blocks the obvious patterns and the pipeline
scans every diff, but neither is a substitute for not doing it. New settings go
into `.env.example` as a name and a placeholder. See [SECURITY.md](SECURITY.md).

## Commits and pull requests

Write commit subjects in the imperative — "Add bottom pager to project tabs",
not "Added" or "Adding". Keep unrelated changes in separate pull requests; a
diff that does one thing is a diff that can be reverted.

The pull request template asks what changed, why, and how it was verified.
"How it was verified" is the one that matters — the pipeline proves the tests
pass, not that the thing you built works.
