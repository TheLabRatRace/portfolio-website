-- ============================================
-- Portfolio Database — Full Schema + Seed
-- Rebuilt from YAML source of truth
-- ============================================

BEGIN;

DROP TABLE IF EXISTS post_tags CASCADE;
DROP TABLE IF EXISTS project_tags CASCADE;
DROP TABLE IF EXISTS attachments CASCADE;
DROP TABLE IF EXISTS gallery_images CASCADE;
DROP TABLE IF EXISTS posts CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS projects CASCADE;

-- ============================================
-- CORE TABLES
-- ============================================

CREATE TABLE projects (
    id              SERIAL PRIMARY KEY,
    type            VARCHAR(20) NOT NULL CHECK (type IN ('work', 'sidequest')),
    category        VARCHAR(20) CHECK (category IN ('infrastructure', 'code')),
    title           VARCHAR(200) NOT NULL,
    slug            VARCHAR(200) NOT NULL UNIQUE,
    description     TEXT,
    long_description TEXT,
    status          VARCHAR(20) CHECK (status IN ('active', 'in_progress')),
    specs           TEXT[],
    display_order   INTEGER DEFAULT 0,
    published       BOOLEAN DEFAULT FALSE,
    -- Where this row's assets live in S3, minus the category segment.
    -- Filled in by 02-schema_admin_search.sql, which runs next on a fresh
    -- volume and backfills any row that arrived without one -- including
    -- every seed row below.
    asset_prefix    VARCHAR(500),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_projects_type ON projects(type);
CREATE INDEX idx_projects_slug ON projects(slug);
CREATE INDEX idx_projects_published ON projects(published);
CREATE INDEX idx_projects_category ON projects(category);

CREATE TABLE tags (
    id    SERIAL PRIMARY KEY,
    name  VARCHAR(64) NOT NULL UNIQUE,
    slug  VARCHAR(64) NOT NULL UNIQUE,
    color VARCHAR(7)
);

CREATE INDEX idx_tags_slug ON tags(slug);

CREATE TABLE posts (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    slug        VARCHAR(200) NOT NULL UNIQUE,
    excerpt     TEXT,
    content     TEXT NOT NULL,
    published   BOOLEAN DEFAULT FALSE,
    -- date is when the author says it went out; created_at is when the row was
    -- written. The list sorts on the first, so a post can be backdated.
    date        DATE,
    display_order INTEGER DEFAULT 0,
    -- Where this row's assets live in S3, minus the category segment.
    -- Filled in by 02-schema_admin_search.sql, which runs next on a fresh
    -- volume and backfills any row that arrived without one -- including
    -- every seed row below.
    asset_prefix VARCHAR(500),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_posts_slug ON posts(slug);
CREATE INDEX idx_posts_published ON posts(published);

-- ============================================
-- JUNCTION TABLES
-- ============================================

CREATE TABLE project_tags (
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    featured    BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (project_id, tag_id)
);

CREATE TABLE post_tags (
    post_id  INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);

-- ============================================
-- CHILD TABLES
-- ============================================

CREATE TABLE gallery_images (
    id              SERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    label           VARCHAR(200),
    thumbnail_path  VARCHAR(500),
    image_path      VARCHAR(500),
    display_order   INTEGER DEFAULT 0
);

CREATE INDEX idx_gallery_project ON gallery_images(project_id);

CREATE TABLE attachments (
    id              SERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    category        VARCHAR(20) NOT NULL CHECK (category IN ('document', 'download')),
    name            VARCHAR(200) NOT NULL,
    file_type       VARCHAR(50),
    file_size       VARCHAR(20),
    url             VARCHAR(500) NOT NULL,
    display_order   INTEGER DEFAULT 0
);

CREATE INDEX idx_attachments_project ON attachments(project_id);
CREATE INDEX idx_attachments_category ON attachments(category);

-- ============================================
-- TRIGGERS
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_projects_updated
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_posts_updated
    BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- SEED: Tags
-- ============================================

INSERT INTO tags (name, slug, color) VALUES
    ('Proxmox',         'proxmox',          '#c9a84c'),
    ('Docker',          'docker',           '#c9a84c'),
    ('Ollama',          'ollama',           '#c9a84c'),
    ('GPU Passthrough', 'gpu-passthrough',  '#c9a84c'),
    ('Splunk',          'splunk',           '#c9a84c'),
    ('AWS',             'aws',              '#c9a84c'),
    ('S3',              's3',               '#c9a84c'),
    ('SNS',             'sns',              '#c9a84c'),
    ('Security',        'security',         '#c9a84c'),
    ('Grafana',         'grafana',          '#c9a84c'),
    ('SNMP',            'snmp',             '#c9a84c'),
    ('Cisco',           'cisco',            '#c9a84c'),
    ('Palo Alto',       'palo-alto',        '#c9a84c'),
    ('API Gateway',     'api-gateway',      '#5b9bd5'),
    ('DynamoDB',        'dynamodb',         '#5b9bd5'),
    ('Lambda',          'lambda',           '#5b9bd5'),
    ('Python',          'python',           '#5b9bd5'),
    ('GitLab',          'gitlab',           '#5b9bd5'),
    ('IAM',             'iam',              '#5b9bd5'),
    ('OIDC',            'oidc',             '#5b9bd5'),
    ('Terraform',       'terraform',        '#5b9bd5'),
    ('OpenClaw',        'openclaw',         '#5b9bd5'),
    ('AWS Bedrock',     'aws-bedrock',      '#5b9bd5'),
    ('Discord',         'discord',          '#5b9bd5'),
    ('ZFS Storage',     'zfs-storage',      '#c9a84c'),
    ('Nginx',           'nginx',            '#c9a84c'),
    ('PostgreSQL',      'postgresql',       '#5b9bd5'),
    ('TLS',             'tls',              '#c9a84c'),
    -- Used by the blog posts below and by no project.
    ('GPU',             'gpu',              '#c9a84c'),
    ('Homelab',         'homelab',          '#c9a84c'),
    ('CloudTrail',      'cloudtrail',       '#c9a84c'),
    ('AI',              'ai',               '#5b9bd5'),
    ('Automation',      'automation',       '#5b9bd5'),
    ('Cost',            'cost',             '#5b9bd5');

-- ============================================
-- SEED: Work Projects (ids 1–6)
-- ============================================

INSERT INTO projects (type, category, title, slug, description, long_description, display_order, published) VALUES
(
    'work', 'infrastructure',
    'Self-Hosted AI Stack',
    'self-hosted-ai-stack',
    'Full AI inference platform on Proxmox with NVIDIA RTX GPU passthrough, running Ollama, Open WebUI, and vector search via Qdrant.',
    'Designed and deployed a complete AI inference platform on a Proxmox VM with NVIDIA RTX 2000E Ada GPU passthrough. The stack runs via Docker Compose orchestrating Ollama for model inference, Open WebUI for the chat interface, Qdrant for vector search, and OpenClaw for multi-agent workflows. Models are managed through Docker bind mounts for persistence, with a curated lineup optimized for the available VRAM budget.',
    1, true
),
(
    'work', 'infrastructure',
    'Splunk CloudTrail Pipeline',
    'splunk-cloudtrail-pipeline',
    'End-to-end CloudTrail ingestion pipeline with S3, SNS triggers, and SPL-based IAM/security alerting dashboards.',
    'Built an end-to-end CloudTrail log ingestion pipeline from AWS into Splunk. CloudTrail writes to S3, SNS notifications trigger ingestion, and SPL queries power dashboards for IAM activity monitoring, S3 access patterns, and security alerting. Debugged an S3 prefix mismatch that was silently breaking SNS notifications — a subtle issue that took careful log analysis to identify.',
    2, true
),
(
    'work', 'infrastructure',
    'Network Monitoring Stack',
    'network-monitoring-stack',
    'SNMP-based monitoring for Cisco switches and Palo Alto firewalls using Grafana Alloy and Datadog integration.',
    'Deployed SNMP-based monitoring across Cisco switches and Palo Alto firewalls using Grafana Alloy as the collection agent with Datadog as a secondary ingestion path. Built custom dashboards for bandwidth utilization, interface health, and firewall policy hits. The lab mirrors production so configs can be validated before rollout.',
    3, true
),
(
    'work', 'code',
    'Serverless API Pipeline',
    'serverless-api-pipeline',
    'Serverless data pipeline POC using AWS API Gateway, DynamoDB, and Python Lambda functions for email-to-database workflows.',
    'Proof-of-concept serverless pipeline that receives inbound data via API Gateway, processes it through Python Lambda functions, and stores results in DynamoDB. Originally designed for an email-to-database workflow, the pattern is reusable for any event-driven data ingestion. Includes IAM policy scoping, API key management, and CloudWatch monitoring.',
    4, true
),
(
    'work', 'code',
    'GitLab CI/CD OIDC Migration',
    'gitlab-cicd-oidc-migration',
    'Migrated CI/CD pipelines from static IAM keys to OIDC-based authentication for improved security posture.',
    'Led the migration of GitLab CI/CD pipelines from static IAM access keys to OIDC-based federation. This eliminated long-lived credentials from the pipeline entirely — runners now assume short-lived IAM roles via OIDC trust policies. The migration included updating Terraform providers, scoping IAM policies to least privilege, and validating the trust chain across multiple AWS accounts.',
    5, true
),
(
    'work', 'code',
    'Discord AI Agent',
    'discord-ai-agent',
    'Multi-agent Discord bot orchestration powered by OpenClaw with AWS Bedrock backend for conversational AI.',
    'Built a multi-agent Discord bot using OpenClaw for orchestration and AWS Bedrock for inference. The system supports multiple specialized agents that can be invoked contextually within Discord channels. Configuration includes IAM role scoping for Bedrock access, model ID routing, and systemd service management for persistent uptime. Also deployed a secondary instance on a Raspberry Pi for testing.',
    6, true
);

-- ============================================
-- SEED: Side Quest Projects (ids 7–11)
-- ============================================

INSERT INTO projects (type, title, slug, description, long_description, status, specs, display_order, published) VALUES
(
    'sidequest',
    'Proxmox Homelab',
    'proxmox-homelab',
    'Full virtualization platform on a Minisforum MS-01 running multiple VMs and containers — the backbone of everything below.',
    'The Minisforum MS-01 serves as the foundation of my entire lab environment. Running Proxmox VE, it hosts a mix of Ubuntu and CentOS VMs alongside LXC containers. Storage is tiered across NVMe SSDs for high-performance workloads and a 5×4TB RAID-Z1 pool for bulk storage. The iGPU is disabled at BIOS level to enable clean PCIe passthrough of the NVIDIA RTX 2000E Ada to a dedicated AI workload VM.',
    'active', ARRAY['Intel 12th Gen', '64GB RAM', 'ZFS Storage', 'LVM Tiered'],
    1, true
),
(
    'sidequest',
    'Self-Hosted AI Stack',
    'homelab-ai-stack',
    'GPU-accelerated AI inference with NVIDIA RTX 2000E Ada passthrough. Running Ollama, Open WebUI, Qdrant vector DB, and OpenClaw for multi-agent orchestration.',
    'The AI stack runs on a dedicated Ubuntu VM (ai01) with full GPU passthrough. Docker Compose orchestrates all services: Ollama handles model inference with a curated lineup (gpt-oss:20b, mistral-small3.2:24b, qwen3:14b, qwen3-coder:30b), Open WebUI provides the chat interface, Qdrant powers vector search, and OpenClaw enables multi-agent workflows with AWS Bedrock integration. Models are managed via Docker bind mounts for persistence across container rebuilds.',
    'active', ARRAY['RTX 2000E Ada', 'Ollama', 'Open WebUI', 'Qdrant', 'OpenClaw'],
    2, true
),
(
    'sidequest',
    'Network Monitoring Lab',
    'network-monitoring-lab',
    'SNMP-based monitoring for Cisco switches and Palo Alto firewalls using Grafana Alloy and Datadog. Testing configs before deploying to production.',
    'This lab mirrors our production monitoring stack so I can test SNMP polling configs, dashboard layouts, and alerting rules before rolling them out. Grafana Alloy collects SNMP metrics from Cisco switches and Palo Alto firewalls, with Datadog as a secondary ingestion path for bandwidth and health monitoring. The goal is zero surprises when changes hit production.',
    'active', ARRAY['Grafana Alloy', 'SNMP', 'Datadog', 'Cisco IOS'],
    3, true
),
(
    'sidequest',
    'Docker Service Fleet',
    'docker-service-fleet',
    'Self-hosted services via Docker Compose — Nextcloud, Wiki.js, Jellyfin, BookStack, PhotoPrism, Portainer, and more.',
    'A growing fleet of self-hosted services, each in its own Docker Compose stack behind an Nginx reverse proxy with automated TLS certificates. PostgreSQL handles persistence for most services. The setup prioritizes data ownership and privacy — everything from file storage (Nextcloud) to documentation (Wiki.js, BookStack) to media (Jellyfin, PhotoPrism) runs locally.',
    'active', ARRAY['Docker Compose', 'Nginx Proxy', 'PostgreSQL', 'TLS'],
    4, true
),
(
    'sidequest',
    'CCNA to CCNP Study Lab',
    'ccna-ccnp-study-lab',
    'Dedicated networking lab environment for hands-on certification prep. VLAN configs, routing protocols, and firewall rules in a safe sandbox.',
    'A sandboxed networking environment for CCNA and CCNP Enterprise certification prep. I configure VLANs, OSPF/EIGRP routing, ACLs, and firewall policies against real Cisco IOS images. The ENAUTO track adds Python-based network automation via RESTCONF/NETCONF. Study blocks are scheduled 8:00–9:30pm weeknights and Saturday mornings.',
    'in_progress', ARRAY['CCNA 200-301', 'ENCOR 350-401', 'ENAUTO 300-435'],
    5, true
);

-- ============================================
-- SEED: Project <-> Tag Associations
-- ============================================

-- Work: Self-Hosted AI Stack (id=1)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (1, 1, true),   -- Proxmox
    (1, 2, true),   -- Docker
    (1, 3, true),   -- Ollama
    (1, 4, true);   -- GPU Passthrough

-- Work: Splunk CloudTrail Pipeline (id=2)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (2, 5, true),   -- Splunk
    (2, 6, true),   -- AWS
    (2, 7, true),   -- S3
    (2, 8, true),   -- SNS
    (2, 9, true);   -- Security

-- Work: Network Monitoring Stack (id=3)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (3, 10, true),  -- Grafana
    (3, 11, true),  -- SNMP
    (3, 12, true),  -- Cisco
    (3, 13, true);  -- Palo Alto

-- Work: Serverless API Pipeline (id=4)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (4, 14, true),  -- API Gateway
    (4, 15, true),  -- DynamoDB
    (4, 16, true),  -- Lambda
    (4, 17, true);  -- Python

-- Work: GitLab OIDC (id=5)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (5, 18, true),  -- GitLab
    (5, 19, true),  -- IAM
    (5, 20, true),  -- OIDC
    (5, 21, true);  -- Terraform

-- Work: Discord AI Agent (id=6)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (6, 17, true),  -- Python
    (6, 22, true),  -- OpenClaw
    (6, 23, true),  -- AWS Bedrock
    (6, 24, true);  -- Discord

-- Sidequest: Proxmox Homelab (id=7)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (7, 1, true),   -- Proxmox
    (7, 25, true),  -- ZFS Storage
    (7, 2, false);  -- Docker

-- Sidequest: Homelab AI Stack (id=8)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (8, 4, true),   -- GPU Passthrough
    (8, 3, true),   -- Ollama
    (8, 22, true),  -- OpenClaw
    (8, 2, false);  -- Docker

-- Sidequest: Network Monitoring Lab (id=9)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (9, 10, true),  -- Grafana
    (9, 11, true),  -- SNMP
    (9, 12, false); -- Cisco

-- Sidequest: Docker Service Fleet (id=10)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (10, 2, true),   -- Docker
    (10, 26, true),  -- Nginx
    (10, 27, true),  -- PostgreSQL
    (10, 28, true);  -- TLS

-- Sidequest: CCNA Study Lab (id=11)
INSERT INTO project_tags (project_id, tag_id, featured) VALUES
    (11, 12, true),  -- Cisco
    (11, 13, false); -- Palo Alto

-- ============================================
-- SEED: Gallery Images
-- ============================================

-- Work: Self-Hosted AI Stack (id=1)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (1, 'Architecture Diagram', 1),
    (1, 'Docker Compose Topology', 2);

-- Work: Splunk CloudTrail Pipeline (id=2)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (2, 'Splunk Dashboard', 1),
    (2, 'Pipeline Architecture', 2);

-- Work: Network Monitoring Stack (id=3)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (3, 'Grafana Dashboard', 1),
    (3, 'Network Topology', 2);

-- Work: Serverless API Pipeline (id=4)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (4, 'API Flow Diagram', 1);

-- Work: GitLab OIDC (id=5)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (5, 'OIDC Auth Flow', 1);

-- Work: Discord AI Agent (id=6)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (6, 'Bot Architecture', 1),
    (6, 'Agent Flow Diagram', 2);

-- Sidequest: Proxmox Homelab (id=7)
INSERT INTO gallery_images (project_id, label, image_path, display_order) VALUES
    (7, 'Proxmox Dashboard', 'PRIVATE_1135x.webp', 1);
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (7, 'Hardware Setup', 2),
    (7, 'Storage Layout', 3);

-- Sidequest: Homelab AI Stack (id=8)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (8, 'Open WebUI Interface', 1),
    (8, 'GPU Utilization Monitoring', 2),
    (8, 'Docker Compose Architecture', 3);

-- Sidequest: Network Monitoring Lab (id=9)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (9, 'Grafana Dashboard', 1),
    (9, 'SNMP Metric Explorer', 2);

-- Sidequest: Docker Service Fleet (id=10)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (10, 'Portainer Overview', 1),
    (10, 'Service Architecture', 2);

-- Sidequest: CCNA Study Lab (id=11)
INSERT INTO gallery_images (project_id, label, display_order) VALUES
    (11, 'Lab Topology', 1);

-- ============================================
-- SEED: Attachments (documents + downloads)
-- ============================================

-- Work: Self-Hosted AI Stack (id=1)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (1, 'document', 'GPU Passthrough Setup Guide', 'Markdown', '/docs/ai-stack/gpu-passthrough-guide', 1),
    (1, 'document', 'Model VRAM Budget Spreadsheet', 'Spreadsheet', '/docs/ai-stack/vram-budget', 2);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (1, 'download', 'docker-compose.yml', 'YAML', '3 KB', '/files/ai-stack/docker-compose.yml', 1);

-- Work: Splunk CloudTrail Pipeline (id=2)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (2, 'document', 'SPL Query Library', 'Markdown', '/docs/splunk/spl-queries', 1),
    (2, 'document', 'CloudTrail Ingestion Runbook', 'PDF', '/docs/splunk/cloudtrail-runbook', 2);

-- Work: Network Monitoring Stack (id=3)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (3, 'document', 'SNMP OID Reference', 'PDF', '/docs/monitoring/snmp-oid-reference', 1);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (3, 'download', 'alloy-config.river', 'Config', '2 KB', '/files/monitoring/alloy-config.river', 1);

-- Work: Serverless API Pipeline (id=4)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (4, 'document', 'API Endpoint Documentation', 'Markdown', '/docs/serverless/api-endpoints', 1),
    (4, 'document', 'IAM Policy Reference', 'PDF', '/docs/serverless/iam-policy', 2);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (4, 'download', 'lambda_handler.py', 'Python', '2 KB', '/files/serverless/lambda_handler.py', 1);

-- Work: GitLab OIDC (id=5)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (5, 'document', 'Migration Checklist', 'PDF', '/docs/gitlab/migration-checklist', 1),
    (5, 'document', 'IAM Trust Policy Template', 'JSON', '/docs/gitlab/iam-trust-policy', 2);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (5, 'download', 'gitlab-ci-oidc.yml', 'YAML', '1 KB', '/files/gitlab/gitlab-ci-oidc.yml', 1);

-- Work: Discord AI Agent (id=6)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (6, 'document', 'Agent Configuration Guide', 'Markdown', '/docs/discord/agent-config', 1);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (6, 'download', 'bot_config.py', 'Python', '3 KB', '/files/discord/bot_config.py', 1);

-- Sidequest: Proxmox Homelab (id=7)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (7, 'document', 'Network Topology Diagram', 'PDF', '/docs/homelab/network-topology', 1),
    (7, 'document', 'VM Inventory & Resource Map', 'Spreadsheet', '/docs/homelab/vm-inventory', 2);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (7, 'download', 'Proxmox Post-Install Script', 'Shell', '4 KB', '/files/homelab/proxmox-post-install.sh', 1);

-- Sidequest: Homelab AI Stack (id=8)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (8, 'document', 'Model Lineup & VRAM Budget', 'Markdown', '/docs/homelab-ai/model-lineup', 1),
    (8, 'document', 'OpenClaw Agent Config Guide', 'PDF', '/docs/homelab-ai/openclaw-config', 2);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (8, 'download', 'docker-compose.yml', 'YAML', '3 KB', '/files/homelab-ai/docker-compose.yml', 1),
    (8, 'download', 'ollama-model-pull.sh', 'Shell', '1 KB', '/files/homelab-ai/ollama-model-pull.sh', 2);

-- Sidequest: Network Monitoring Lab (id=9)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (9, 'document', 'SNMP OID Reference Sheet', 'PDF', '/docs/monitoring-lab/snmp-oid-reference', 1);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (9, 'download', 'alloy-config.river', 'Config', '2 KB', '/files/monitoring-lab/alloy-config.river', 1);

-- Sidequest: Docker Service Fleet (id=10)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (10, 'document', 'Service Inventory', 'Markdown', '/docs/docker-fleet/service-inventory', 1);
INSERT INTO attachments (project_id, category, name, file_type, file_size, url, display_order) VALUES
    (10, 'download', 'nginx-proxy-template.conf', 'Config', '2 KB', '/files/docker-fleet/nginx-proxy-template.conf', 1);

-- Sidequest: CCNA Study Lab (id=11)
INSERT INTO attachments (project_id, category, name, file_type, url, display_order) VALUES
    (11, 'document', 'Study Plan & Timeline', 'PDF', '/docs/ccna/study-plan', 1),
    (11, 'document', 'ENCOR Topic Checklist', 'Spreadsheet', '/docs/ccna/encor-checklist', 2);

-- ============================================
-- SEED: Blog Posts
-- ============================================
--
-- Seeded here for the same reason the projects are: this file is what a fresh
-- database is built from, and a blog that starts with nothing in it is not a
-- fresh install, it is a broken one.
--
-- These used to live in data/blog.yaml behind an importer, because the two
-- copies had drifted and the YAML was the one the site served. Deleting the
-- losing copy fixed that; keeping the importer would have left the same two
-- sources with a script between them.

INSERT INTO posts (title, slug, excerpt, content, date, display_order, published) VALUES
    ('GPU Passthrough on Proxmox: What I Wish I Knew',
     'gpu-passthrough-proxmox',
     'Getting NVIDIA RTX passthrough working on a Minisforum MS-01 wasn''t plug-and-play. Here''s every BIOS setting, kernel parameter, and gotcha I hit along the way.',
     'This is a placeholder for the full blog post. Replace this with your actual content — markdown rendering, rich text, or even a fetch from a CMS or static files.',
     '2026-04-28', 0, TRUE),
    ('Debugging a Silent Failure: S3 Prefix Mismatches in Splunk Ingestion',
     'splunk-s3-prefix-mismatch',
     'Our CloudTrail logs just stopped showing up in Splunk. No errors, no alerts. The root cause was a one-character S3 prefix mismatch that broke SNS notifications.',
     'This is a placeholder for the full blog post. Replace this with your actual content.',
     '2026-04-14', 1, TRUE),
    ('From Static Keys to OIDC: Securing GitLab CI/CD on AWS',
     'gitlab-oidc-aws',
     'Static IAM keys in CI/CD pipelines are a liability. Here''s how I migrated our GitLab runners to OIDC federation — and why it''s worth the effort.',
     'This is a placeholder for the full blog post. Replace this with your actual content.',
     '2026-03-22', 2, TRUE),
    ('Building a Python Automation Toolkit for Infrastructure',
     'python-automation-toolkit',
     'A collection of Python scripts I use daily — from EC2 inventory snapshots to Splunk forwarder health checks. Nothing fancy, just reliable.',
     'This is a placeholder for the full blog post. Replace this with your actual content.',
     '2026-03-08', 3, TRUE),
    ('Self-Hosting AI: Running Ollama at Home vs. Paying for APIs',
     'self-hosting-ai-ollama',
     'I run my own AI inference stack on a single GPU. Here''s a real cost comparison against API pricing, plus the intangibles you can''t put a dollar amount on.',
     'This is a placeholder for the full blog post. Replace this with your actual content.',
     '2026-02-19', 4, TRUE);

-- ============================================
-- SEED: Post <-> Tag Associations
-- ============================================
--
-- Joined on slug rather than on literal ids: the posts above take whatever the
-- sequence hands them, and a slug is the one identifier both sides already
-- agree on.

INSERT INTO post_tags (post_id, tag_id)
SELECT p.id, t.id FROM posts p, tags t
WHERE p.slug = 'gpu-passthrough-proxmox' AND t.slug IN ('proxmox', 'gpu', 'homelab');

INSERT INTO post_tags (post_id, tag_id)
SELECT p.id, t.id FROM posts p, tags t
WHERE p.slug = 'splunk-s3-prefix-mismatch' AND t.slug IN ('splunk', 'aws', 'cloudtrail');

INSERT INTO post_tags (post_id, tag_id)
SELECT p.id, t.id FROM posts p, tags t
WHERE p.slug = 'gitlab-oidc-aws' AND t.slug IN ('gitlab', 'oidc', 'iam', 'security');

INSERT INTO post_tags (post_id, tag_id)
SELECT p.id, t.id FROM posts p, tags t
WHERE p.slug = 'python-automation-toolkit' AND t.slug IN ('python', 'automation', 'aws');

INSERT INTO post_tags (post_id, tag_id)
SELECT p.id, t.id FROM posts p, tags t
WHERE p.slug = 'self-hosting-ai-ollama' AND t.slug IN ('ai', 'ollama', 'homelab', 'cost');

COMMIT;
