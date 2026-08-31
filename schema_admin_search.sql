-- ============================================================
-- Admin + search schema.
--
-- Every statement here is idempotent, because this file has two
-- consumers that cannot be kept in step any other way:
--
--   1. A fresh volume. docker-compose mounts it into
--      /docker-entrypoint-initdb.d as 02-, so Postgres runs it
--      straight after migrate.sql on first boot.
--   2. A database that already has data. migrate.sql only ever
--      runs on an empty volume, so a live stack needs the same
--      DDL applied without being destroyed:
--
--          docker compose exec -T db psql -U postgres -d postgres \
--              < schema_admin_search.sql
--
-- Writing it once and running it twice is the only way both paths
-- stay identical. Add new DDL here, never to migrate.sql.
-- ============================================================

-- ── Admin users ──────────────────────────────────────────────
-- No row is created here. Passwords are set through
-- `flask create-admin`, which hashes them; a seeded default
-- credential in a SQL file is a published credential.
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    email         VARCHAR(200),
    password_hash VARCHAR(256) NOT NULL,
    is_admin      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ── About-page content ───────────────────────────────────────
-- Skills and certifications were the last two things the site
-- read off disk. They are content -- they change when a course
-- finishes, not when the code does -- so they are rows now, and
-- /admin/skills and /admin/certifications are how they change.
--
-- The DDL is here rather than in migrate.sql for the reason at
-- the top of this file: these tables have to appear in a
-- database that already has data, and migrate.sql only ever
-- runs on an empty one.

CREATE TABLE IF NOT EXISTS skills (
    -- The group heading lives on the skill rather than in a table of
    -- its own. Four groups of four is not a hierarchy worth a join,
    -- and a category with nothing in it should stop being rendered,
    -- which a plain column gets right for free.
    id            SERIAL PRIMARY KEY,
    category      VARCHAR(80)  NOT NULL,
    name          VARCHAR(200) NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (category, name)
);

CREATE INDEX IF NOT EXISTS idx_skills_order ON skills(display_order, id);

CREATE TABLE IF NOT EXISTS certifications (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(200) NOT NULL UNIQUE,
    issuer        VARCHAR(120) NOT NULL,
    -- The three the stylesheet has a dot colour for. A fourth value
    -- renders an invisible dot, so the constraint is the check.
    status        VARCHAR(20) NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'in_progress', 'expired')),
    year          INTEGER,
    display_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_certifications_order
    ON certifications(display_order, id);

-- ON CONFLICT, not a guard: this file runs against a live database
-- too, where an edit made in /admin must survive it.
INSERT INTO skills (category, name, display_order) VALUES
    ('Cloud & Infrastructure', 'AWS (EC2, S3, RDS, IAM, SSM, Lambda, API Gateway)',  0),
    ('Cloud & Infrastructure', 'Proxmox / Virtualization',                            1),
    ('Cloud & Infrastructure', 'Docker & Docker Compose',                             2),
    ('Cloud & Infrastructure', 'Terraform / Terragrunt',                              3),
    ('Monitoring & Security',  'Splunk (SPL, Universal Forwarders, TLS)',             4),
    ('Monitoring & Security',  'Grafana / Datadog',                                   5),
    ('Monitoring & Security',  'SNMP Monitoring',                                     6),
    ('Monitoring & Security',  'CloudTrail / IAM Auditing',                           7),
    ('Networking',             'Cisco IOS (CCNA → CCNP track)',                    8),
    ('Networking',             'Palo Alto Firewalls',                                 9),
    ('Networking',             'VLANs / Routing / Switching',                        10),
    ('Networking',             'iSCSI / NFS Storage',                                11),
    ('Development',            'Python scripting & automation',                      12),
    ('Development',            'Java / Spring Boot / Tomcat',                         13),
    ('Development',            'Bash / Shell scripting',                             14),
    ('Development',            'Git / GitLab CI/CD',                                 15)
ON CONFLICT (category, name) DO NOTHING;

INSERT INTO certifications (name, issuer, status, year, display_order) VALUES
    ('AWS Certified Solutions Architect – Associate', 'Amazon Web Services', 'active', 2024, 0),
    ('Cisco Certified Network Associate (CCNA)',         'Cisco',               'active', 2023, 1),
    ('CompTIA Security+',                                'CompTIA',             'active', 2023, 2),
    ('Splunk Core Certified Power User',                 'Splunk',              'active', 2024, 3)
ON CONFLICT (name) DO NOTHING;

-- ── Posts gain the columns the blog templates already read ───
-- The templates render post.date; the table only had created_at,
-- which is when the row was written, not when the piece was
-- published. They are different facts and the author controls one.
ALTER TABLE posts ADD COLUMN IF NOT EXISTS date DATE;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;

UPDATE posts SET date = created_at::date WHERE date IS NULL;

CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(date DESC);

-- ── Full-text search ─────────────────────────────────────────
-- Stored generated columns, not triggers: Postgres recomputes the
-- vector as part of the INSERT/UPDATE that changed the row, so the
-- index can never drift from the content the way a trigger someone
-- forgets to install can.
--
-- The price of that guarantee is that every expression must be
-- IMMUTABLE, and two of the obvious ones are not:
--
--   to_tsvector('english', x) is merely STABLE. The bare literal is
--   an untyped string that Postgres resolves to a regconfig at run
--   time, and that lookup reads search_path. Spelling the cast out
--   -- 'english'::regconfig -- resolves it at parse time instead,
--   and only then is the two-argument form IMMUTABLE.
--
--   array_to_string(text[], text) is declared STABLE for the general
--   case, because an arbitrary element type may have a volatile
--   output function. text's is not one of those, so the wrapper
--   below is a true claim for text[] and for nothing wider. Editing
--   its body would NOT recompute the vectors already stored against
--   it, so it must never be edited: it joins with a space, and that
--   is the whole contract.
CREATE OR REPLACE FUNCTION text_array_join(text[]) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
    AS $fn$ SELECT array_to_string($1, ' ') $fn$;

-- The weights are the ranking. A term in the title (A) outranks the
-- same term in a summary (B), which outranks the body (C). Without
-- them every match on a 2,000-word post beats an exact title hit.

ALTER TABLE projects ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english'::regconfig, coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english'::regconfig, coalesce(description, '')), 'B') ||
        setweight(to_tsvector('english'::regconfig, coalesce(long_description, '')), 'C') ||
        setweight(to_tsvector('english'::regconfig,
                  coalesce(text_array_join(specs), '')), 'C')
    ) STORED;

ALTER TABLE posts ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english'::regconfig, coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english'::regconfig, coalesce(excerpt, '')), 'B') ||
        setweight(to_tsvector('english'::regconfig, coalesce(content, '')), 'C')
    ) STORED;

-- A gallery image is only its label, so there is nothing to weight.
ALTER TABLE gallery_images ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english'::regconfig, coalesce(label, ''))
    ) STORED;

-- GIN, not GiST: this index is read constantly and written rarely,
-- which is exactly the trade GIN makes.
CREATE INDEX IF NOT EXISTS idx_projects_search ON projects USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_posts_search    ON posts    USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_gallery_search  ON gallery_images USING GIN (search_vector);

-- Tag names are matched by substring, not by stem -- someone typing
-- "prox" should find the Proxmox tag. That is a trigram job, and it
-- needs the extension.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_tags_name_trgm ON tags USING GIN (name gin_trgm_ops);
