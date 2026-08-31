# personal_site_v2

A development copy of the portfolio site, fully isolated from V1. Break this one.

## Why it exists

V1 (`../personal_site`) is the real site and holds only its original content:
11 projects seeded from `migrate.sql`. Scale experiments, content generation,
and redesign work happen here instead, so V1's data is never touched.

## Isolation boundaries

| | V1 | V2 |
|---|---|---|
| directory | `../personal_site` | `.` |
| compose project | `personal_site` | `personal_site_v2` |
| database volume | `personal_site_pgdata` | `personal_site_v2_pgdata_v2` |
| host port | 5002 | 5003 |
| memory limit | none | 2 GiB |
| stress tooling | none | `tools/seed_stress.py` |
| stress images | none | `app/static/images/stress/` (400 files, not committed) |

The two stacks share no volume, no network, and no container. A `docker compose`
command run in this directory cannot reach V1's database.

## Running

    cp .env.example .env             # then edit it; see Configuration below
    docker compose up -d --build     # http://localhost:5003

Both sites can run at once; compare them side by side on 5002 and 5003.

## Configuration

Every setting is an environment variable. `.env.example` lists all of them with
placeholder values and is the only file in the repo that mentions them; `.env`
itself is gitignored and must never be committed.

| variable | purpose |
|---|---|
| `SECRET_KEY` | Flask session signing. **Required in production — the app refuses to boot without it.** |
| `DATABASE_URL` | Postgres DSN. Compose builds this itself from `POSTGRES_PASSWORD`. |
| `POSTGRES_PASSWORD` | Password for the local `db` service. |
| `RDS_DATABASE_URL` | The AWS RDS DSN. **Required** — compose will not start without it. |
| `TEST_DATABASE_URL` | Where `pytest` writes. Compose pins it to the local `db`. |
| `PORT` | Host port the container publishes on. Defaults to 5003. |
| `DEV_RELOAD` | Hot-reloads templates and stops caching static assets. Local only. |
| `SHOW_PAGE_TITLE` | Big serif page headings on or off. |
| `S3_BUCKET` | Set it and uploads go to S3; leave it empty and they go to disk. |
| `S3_REGION` | Bucket region. `us-east-2` for `thelabratrace-assets`. |
| `S3_PUBLIC_BASE_URL` | CDN or public bucket origin. Empty means presigned URLs. |
| `S3_URL_EXPIRY_SECONDS` | Lifetime of a presigned URL. Default one hour. |
| `S3_OBJECT_ACL` | Only for buckets that still have ACLs enabled. Usually empty. |

AWS keys are deliberately **not** in that table. boto3 reads
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from the environment, `~/.aws`,
or an instance role, so no credential ever has to sit in a file this repo can
see. `config.py` never reads one.

### SECRET_KEY is a boot condition

Flask signs the session cookie with `SECRET_KEY`. Anyone who knows the value
can forge a cookie that asserts any user id and `is_admin`, which walks past
the admin login without a password — so a default committed to a public
repository is not untidy, it is a working bypass.

There is therefore **no fallback** in `config.py`. `create_app("production")`
raises at startup if the key is empty or one of the known placeholders, before
a single request is served. Development and testing name their own throwaway
keys, which is safe precisely because production will not accept them.

```bash
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))" >> .env
```

`.env` is gitignored. Rotating the key signs every admin out, which is also
what you want the moment you suspect it leaked.

## The database

AWS RDS is what the app talks to. The local Postgres still runs beside it,
because that is what the test suite writes to.

```bash
docker compose up -d                                                        # RDS
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d      # local
```

The local override is for breaking things: seed junk, drop a table, try a
migration. Nothing in it reaches the database the site serves from.

### The suite does not follow the app

`pytest` runs against `TEST_DATABASE_URL`, which `docker-compose.yml` pins to
the `db` container — not `DATABASE_URL`, which now names RDS. Two separate
variables, because the distance between a stray `pytest` and the real rows
should not be one exported environment variable.

The fixtures do roll every write back, but that is a convention: a test that
opens its own engine, or a run killed mid-transaction, walks straight past it.
So `create_app("testing")` refuses outright to start against a remote host,
and one test asserts that the run it is part of is itself pointed somewhere
local. Nothing needs `-f docker-compose.local.yml` to run the suite safely.

### The application is not the master user

`portfolio_app` is a plain login role with `SELECT, INSERT, UPDATE, DELETE` on
the tables and `USAGE, SELECT` on the sequences. It has no superuser bit, and
no `CREATE` on the database or on schema `public`:

```
=> create table nope(i int);
ERROR:  permission denied for schema public
```

Schema changes are therefore a deliberate act by the master user running
`migrate.sql` and `schema_admin_search.sql` by hand, not something a
compromised web process can do. `ALTER DEFAULT PRIVILEGES` grants the app role
the same DML on tables the master user creates later, so a new table does not
silently become invisible to the app.

### verify-full is a boot condition

The instance answers on a public address, so certificate validation is the
only thing standing between the app's password and anyone who can win the DNS
or routing race for that hostname. `sslmode=require` does not help: it
encrypts the connection and validates nothing, so an impostor gets an
encrypted channel and the credentials. Only `verify-full` checks the chain
*and* the hostname, and it needs a trust store to check against.

`create_app("production")` refuses to start if `DATABASE_URL` names a remote
host without `sslmode=verify-full` and an `sslrootcert` — the same fail-closed
treatment `SECRET_KEY` gets, for the same reason: a connection that silently
downgrades looks exactly like one that did not.

`certs/global-bundle.pem` is AWS's published list of RDS CA certificates. It
holds no keys, which is why it is the one file the `*.pem` rule in
`.gitignore` un-ignores; refresh it from
`https://truststore.pki.rds.amazonaws.com/global-bundle.pem`. Compose mounts
it read-only at `/app/certs/global-bundle.pem`.

### Bringing up a fresh instance

As the master user, against a database that does not exist yet:

```sql
CREATE DATABASE portfolio;
CREATE ROLE portfolio_app WITH LOGIN PASSWORD '...';
REVOKE ALL ON DATABASE portfolio FROM PUBLIC;
GRANT CONNECT ON DATABASE portfolio TO portfolio_app;
```

Then, connected to `portfolio`:

```bash
psql "$DSN" -v ON_ERROR_STOP=1 -f migrate.sql
psql "$DSN" -v ON_ERROR_STOP=1 -f schema_admin_search.sql
```

```sql
GRANT USAGE ON SCHEMA public TO portfolio_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO portfolio_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO portfolio_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO portfolio_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO portfolio_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
```

`migrate.sql` seeds content but no admin user — create that with the
`create-admin` step under **Admin and search**. Both files are RDS-safe: the
only privileged statement in either is `CREATE EXTENSION pg_trgm`, which is on
Amazon's allow-list for the master user.

## Seeding content

`migrate.sql` builds the schema and seeds every piece of real content: the 11
projects, the 5 blog posts, and their tags. `schema_admin_search.sql` adds the
admin and search schema on top, plus the skills and certifications the About
section reads. Between them a fresh database is a complete site.

Both run automatically on an empty volume — compose mounts them into
`/docker-entrypoint-initdb.d`. Nothing else needs loading, and there is no
importer to remember: every content type lives in Postgres and is edited
through `/admin`.

    # generate work + sidequest projects with galleries and attachments
    docker compose exec -T web python - --work 200 --quests 150 < tools/seed_stress.py

    # also point galleries at the 400 real image files
    docker compose exec -T web python - --work 200 --quests 150 --image-files 400 < tools/seed_stress.py

    # remove everything generated, back to the 11-project seed
    docker compose exec -T web python - --reset < tools/seed_stress.py

Generated rows carry a `stress-` slug prefix. `--reset` deletes only those,
cascading to their gallery images and attachments; the original 11 projects
from `migrate.sql` survive it.

`tools/backfill_image_paths.py` attaches the generated image files to those
rows so the gallery actually renders, and `--clear` reverses it. It matches on
the `stress-` prefix, so the real portfolio rows are never touched.

## Admin and search

Everything on the site — work, side quests, gallery images, posts, tags — is
edited through `/admin`, behind a login. There is no seed user and no default
password; create the first account yourself:

    docker compose exec -it web flask create-admin

`-it`, not `-T`: the command reads the password from a TTY and refuses to run
without one, so the password is never a shell argument that lands in history or
in a process list. Two companions to it:

    docker compose exec -it web flask reset-password <username>
    docker compose exec -T  web flask list-admins

The whole blueprint is gated by a single `before_request`, so a route added to
it is protected by default and exposing one takes a deliberate edit. Signing in
is not sufficient — a user without `is_admin` gets a 403, not a dashboard.

Readers find content through `/search?q=`, which is Postgres full-text search
over projects, side quests, gallery labels and post bodies. Each table carries
a generated `search_vector` column with a GIN index (`schema_admin_search.sql`),
so ranking is `ts_rank` against weights baked in at write time: a title hit
outranks a summary hit outranks a body hit. Two consequences are worth knowing
before filing a bug:

* **Matching is by stem, not substring.** `deploying` finds `deploy`; `prox`
  does not find `Proxmox`. Tags cover the half-typed case separately, through a
  trigram index, because a tag name is the thing people actually half-type.
* **Unpublished content is invisible.** Every query filters on `published`, so
  a draft cannot leak its title through the search box.

Results are grouped by type rather than interleaved, because a relevance score
is not comparable across tables — a 200-word project and a 2,000-word post
normalise differently, and one merged list would be sorted by length.

## Images and srcset

Gallery cards are ~347 CSS px wide; the source images are 1135px. Every image
therefore ships a width ladder, and the browser picks from it:

    python tools/gen_image_variants.py            # write 360/540/720/1080 variants
    python tools/gen_image_variants.py --prune    # ...and delete orphaned ones

The tool needs `cwebp` (`brew install webp`) and writes
`app/static/images/variants.json`. `create_app` reads that manifest once at
startup and exposes it to templates as `image_srcset()`. An image with no entry
simply gets no `srcset` and still renders from its plain `src`.

Two consequences worth knowing:

* **`variants.json` is committed.** The runtime image has no `cwebp`, so it
  cannot rebuild the manifest. Regenerate it on the host and commit the result.
* **`app/static/images/stress/` is not committed.** It is 19 MB of synthetic
  imagery that is reproducible in one command. After regenerating it, re-run
  the variant tool so the manifest matches what is on disk.

## Asset hosting

Images, video and audio live in the `thelabratrace-assets` S3 bucket, laid out
`<Category>/<Application>/<Section>/...` so one bucket can serve more than this
site:

    Images/Portfolio-Site/Blog/2026/08/30/gpu-passthrough-proxmox/cover.webp
    Images/Portfolio-Site/Projects/Work/2026/08/30/splunk-pipeline/rack.webp
    Images/Portfolio-Site/Projects/SideQuests/...
    Images/Portfolio-Site/Home/            # no date; the page has one set
    Images/Portfolio-Site/Contact/

`app/services/assets.py` is the only place that knows this layout. Dated
sections put `YYYY/MM/DD` before the slug so a prefix listing is chronological
without a sort and two posts published the same day cannot collide -- S3 has no
directories, so a second post on the same day needs no check, it just writes a
key that shares the first eight segments.

**Every post and project gets a prefix when it is created**, upload or no
upload, stored in `asset_prefix` as the category-less tail
(`Portfolio-Site/Blog/2026/08/30/slug`). One column answers for all three
categories; `row.asset_prefixes` puts `Images/`, `Video/` and `Audio/` back.
A `before_insert` hook assigns it, so the admin form, the CLI and a seed
script all behave the same. A prefix is never reassigned: objects already sit
under it, and rewriting the column on a rename would orphan them.

### Two backends, one column

| `S3_BUCKET` | uploads go to | database stores |
|---|---|---|
| set | the bucket, under the row's prefix | `s3:Images/Portfolio-Site/...` |
| empty | `app/static/images/uploads/` | `uploads/<token>.webp` |

The `s3:` marker is what lets one `VARCHAR(500)` hold both, so rows written
before this feature existed still resolve and nothing had to be migrated.
Templates call `asset_url(path)` and never `url_for('static', ...)` -- adding a
third backend later is one function, not five templates.

A fresh checkout with no AWS account gets the local backend and everything
works, which is also what CI and the test suite use (`TestingConfig` pins
`S3_BUCKET` empty so a developer with the variable exported cannot make the
suite upload to a real bucket).

### Seeding the bucket

```bash
docker compose exec -T web python tools/seed_s3_placeholders.py --check
docker compose exec -T web python tools/seed_s3_placeholders.py --dry-run
docker compose exec -T web python tools/seed_s3_placeholders.py --commit
```

`--check` probes list, put and delete and stops. Nothing is written without
`--commit`, and re-running skips objects that are already there.

The IAM user needs, at minimum:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::thelabratrace-assets" },
    { "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::thelabratrace-assets/*" }
  ]
}
```

## Testing

    docker compose exec -T web python -m pytest -q

The suite runs against a real Postgres, not SQLite, and that is deliberate:
search is a generated `tsvector` column with `websearch_to_tsquery` behind it,
and none of that exists on another engine. A search suite that passed on SQLite
would be testing something the site does not ship. It also needs the seed —
`test_blog_post` asserts a real post returns 200 — so run it against the
compose stack rather than a bare checkout.

Which means the tests point at your dev database. **No test is allowed to leave
a row behind.** The `db_session` fixture in `tests/conftest.py` runs each test
inside a transaction that is always rolled back, and every test that writes
takes that fixture. Binding it correctly is subtler than it looks: Flask-
SQLAlchemy 3.1 overrides `Session.get_bind()` to resolve the engine from
`db.engines`, so a bind passed to `session.configure()` is silently ignored and
the session keeps writing to the real database — a green suite that quietly
seeds your dev data. Swapping the entry in `db.engines` is what actually
redirects it. If you add a fixture that writes, verify the row counts are
unchanged afterwards rather than trusting that it rolled back.

| file | covers |
|---|---|
| `tests/test_routes.py` | the public pages answer |
| `tests/test_auth.py` | the credential check, the session, `?next=` open-redirect refusal, CSRF |
| `tests/test_admin.py` | the authorisation gate, and that editing writes what the form says |
| `tests/test_search.py` | ranking, stemming, hostile input, and that drafts stay invisible |

`TestingConfig` disables CSRF so tests can post forms without fetching a token
first; `test_csrf_is_enforced_when_enabled` turns it back on and checks a
tokenless POST is rejected, because a protection only ever switched off in
tests is a protection nobody has tested.

## CI

`.github/workflows/ci.yml` runs on every push to `main`, every tag, and every
pull request:

| job | what it proves |
|---|---|
| `secret scan` | nothing credential-shaped is anywhere in the history — gitleaks, run with `--redact` so a finding is reported without reprinting the secret |
| `lint (ruff)` | `ruff check` over `app`, `config.py`, `run.py`, `tools`, `tests`, reported as inline annotations on the diff |
| `lint (templates)` | every one of the 32 Jinja templates compiles |
| `lint (deps, advisory)` | `pip-audit` over `requirements.txt` — never blocks |
| `test (pytest)` | the suite, against a throwaway Postgres seeded exactly as a fresh install is: `migrate.sql` then `schema_admin_search.sql` |
| `build image` | the Dockerfile builds, the container answers on `/`, the image pushes |

Pushes to `main` and pull requests are separate triggers rather than one
combined rule, so a branch with an open PR runs the pipeline once, not twice.
`build image` builds and smoke-tests on a pull request but only pushes to the
registry from `main` or a tag.

Lint rules live in `ruff.toml`. The selected set (`E`, `F`, `W`) is the part
that is already green; `I`, `DTZ` and `SIM` are documented there as deferred,
each because it wants a code change rather than a lint fix.

## Deploying

The pipeline publishes `ghcr.io/thelabratrace/portfolio-website:<short-sha>`,
plus `:latest` from `main` and `:<tag>` from a tag. Anything the running
container needs — a real `DATABASE_URL`, a production `SECRET_KEY` — belongs in
**Settings ▸ Secrets and variables ▸ Actions**, and is referenced by name only.
No credential is ever written into a file in this repository.

## Known ceilings (measured before the V2 fixes)

Everything on `/projects/` used to be linear in project count, because the
template pre-rendered a detail panel for every project in one response:

| projects | response | TTFB | last row visible at |
|---|---|---|---|
| 11 | 0.10 MB | 0.057s | 0.5s |
| 511 | 5.51 MB | 0.334s | 18.5s |
| 3,011 | 32.54 MB | 2.280s | 108.4s |
| 6,011 | 65.08 MB | 5.168s | 216.4s |

All three root causes have since been fixed in V2:

1. `app/templates/projects/list.html` — the unbounded fade stagger is gone and
   detail panels are fetched on click from `/projects/panel/<slug>` instead of
   being rendered inline.
2. `app/models/` — the three relationships use `lazy="selectin"`, so the
   cartesian product is gone. `tools/ab_loaders.py` measures the difference.
3. `app/blueprints/projects/routes.py` — the listing paginates (10 per
   page, per tab) and `/projects/<slug>` exists as a real route.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues go to
[SECURITY.md](SECURITY.md) instead of the issue tracker.

## Licence

None yet — all rights reserved by default. Add a `LICENSE` file if this
repository is ever made public.

## Assets

```bash
# regenerate app/static/css/style.min.css after editing style.css
python3 tools/minify_css.py
```
