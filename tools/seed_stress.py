"""Bulk-generate portfolio content to stress-test the projects page.

The projects view renders every project, every side quest, and a full detail
panel for each in a single response, so page cost scales linearly with row
count. This tool loads a chosen volume so that cost can be measured.

Usage (from the host, piped into the running web container):
    docker compose exec -T web python - --work 200 --quests 150 < tools/seed_stress.py

Generated rows are marked with a 'stress-' slug prefix so --reset can remove
them without touching the original seed data from migrate.sql.
"""

import argparse
import os
import random

import psycopg2
from psycopg2.extras import execute_values

SLUG_PREFIX = "stress-"

SYSTEMS = [
    "Kubernetes Cluster", "Splunk Pipeline", "Proxmox Node", "Terraform Module",
    "GitLab Runner", "Grafana Stack", "Ceph Pool", "Vault Cluster", "NGINX Edge",
    "Postgres Replica", "Redis Cache", "Kafka Broker", "Ansible Playbook",
    "Wireguard Mesh", "OPNsense Firewall", "TrueNAS Array", "Docker Swarm",
    "Prometheus Federation", "Loki Ingester", "MinIO Gateway", "Consul Mesh",
    "Nomad Scheduler", "Cilium Overlay", "ArgoCD Sync", "Harbor Registry",
    "Elastic Ingest", "Zabbix Proxy", "Netbox Inventory", "PowerDNS Zone",
    "Squid Proxy", "HAProxy Frontend", "Keepalived Pair", "ZFS Snapshot Chain",
    "Cisco Access Layer", "Palo Alto Policy", "S3 Lifecycle Rule",
    "Lambda Fanout", "API Gateway Stage", "CloudTrail Lake", "IAM Boundary",
]

ACTIONS = [
    "Automating", "Hardening", "Migrating", "Instrumenting", "Rebuilding",
    "Benchmarking", "Decomposing", "Federating", "Replicating", "Draining",
    "Rotating", "Tiering", "Bootstrapping", "Rightsizing", "Air-gapping",
]

QUALIFIERS = [
    "at Scale", "Without Downtime", "on a Budget", "for Compliance",
    "in Anger", "the Hard Way", "with Zero Trust", "Across Regions",
    "Behind a Firewall", "on Bare Metal", "for Real This Time", "in Production",
]

TAG_POOL = [
    "Proxmox", "Docker", "Ollama", "GPU Passthrough", "Splunk", "AWS", "S3",
    "SNS", "Security", "Grafana", "Terraform", "Ansible", "Kubernetes", "Ceph",
    "ZFS", "Vault", "GitLab", "IAM", "OIDC", "Postgres", "Redis", "Kafka",
    "Prometheus", "Loki", "NGINX", "HAProxy", "Cisco", "Palo Alto", "VLAN",
    "BGP", "Wireguard", "Netbox", "Zabbix", "Datadog", "Lambda", "Python",
    "Bash", "Go", "Observability", "Networking", "Storage", "Automation",
]

IMAGE_LABELS = [
    "Architecture Diagram", "Grafana Dashboard", "Rack Elevation",
    "Network Topology", "Terminal Session", "Failover Test", "Latency Heatmap",
    "Storage Layout", "Traffic Flow", "Alert Timeline", "Capacity Plan",
    "Console Output", "Wiring Diagram", "Throughput Graph", "Cutover Runbook",
]

DOC_NAMES = [
    "Runbook", "Design Doc", "Postmortem", "Migration Plan", "Threat Model",
    "Capacity Model", "Test Report", "Rollback Procedure", "Network Diagram",
]

DL_NAMES = [
    "docker-compose.yml", "main.tf", "playbook.yml", "values.yaml",
    "deploy.sh", "alerts.rules", "dashboard.json", "schema.sql", "Makefile",
]

LOREM = (
    "Built and validated this in the lab before touching production. The rollout "
    "covered configuration management, monitoring coverage, and a documented "
    "rollback path. Failure modes were exercised deliberately: node loss, network "
    "partition, and a full restore from cold storage. Metrics went to Grafana and "
    "alerts routed through the on-call rotation. "
)


def build_project(index, kind, rng):
    """Return a row tuple for one generated project."""
    system = rng.choice(SYSTEMS)
    if kind == "work":
        title = f"{rng.choice(ACTIONS)} the {system} {rng.choice(QUALIFIERS)}"
        category = rng.choice(["infrastructure", "code"])
        status = None
        specs = None
    else:
        title = f"{system} {rng.choice(QUALIFIERS)}"
        category = None
        status = rng.choice(["active", "in_progress"])
        specs = rng.sample(
            ["64GB RAM", "ZFS Storage", "10GbE", "NVMe Tier", "RAID-Z1",
             "Intel 12th Gen", "RTX 2000E Ada", "LXC", "Dual PSU", "IPMI"],
            k=rng.randint(3, 5),
        )

    slug = f"{SLUG_PREFIX}{kind}-{index:05d}"
    description = (
        f"{system} work covering deployment, monitoring, and the failure modes "
        f"that only show up once real traffic lands on it."
    )
    long_description = LOREM * rng.randint(2, 5)
    return (kind, category, f"{title} #{index}", slug, description,
            long_description, status, specs, index, True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=int, default=200)
    ap.add_argument("--quests", type=int, default=150)
    ap.add_argument("--images", type=int, default=3, help="gallery images per project")
    ap.add_argument("--attachments", type=int, default=5, help="attachments per project")
    ap.add_argument("--image-files", type=int, default=0,
                    help="how many distinct real image paths to cycle through")
    ap.add_argument("--reset", action="store_true", help="delete generated rows and exit")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    dsn = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    if args.reset:
        cur.execute("DELETE FROM projects WHERE slug LIKE %s", (SLUG_PREFIX + "%",))
        removed = cur.rowcount
        conn.commit()
        print(f"deleted {removed} generated projects (cascade cleared children)")
        return

    # Tags are shared, so top the pool up once and reuse ids.
    execute_values(
        cur,
        "INSERT INTO tags (name, slug, color) VALUES %s ON CONFLICT DO NOTHING",
        [(t, t.lower().replace(" ", "-"), "#c9a84c") for t in TAG_POOL],
    )
    cur.execute("SELECT id FROM tags")
    tag_ids = [r[0] for r in cur.fetchall()]

    rows = []
    for i in range(args.work):
        rows.append(build_project(i + 1, "work", rng))
    for i in range(args.quests):
        rows.append(build_project(i + 1, "sidequest", rng))

    execute_values(
        cur,
        """INSERT INTO projects
           (type, category, title, slug, description, long_description,
            status, specs, display_order, published)
           VALUES %s""",
        rows,
        page_size=500,
    )
    # execute_values batches, and RETURNING only yields the final batch --
    # read the ids back instead so every generated project gets children.
    cur.execute("SELECT id FROM projects WHERE slug LIKE %s", (SLUG_PREFIX + "%",))
    project_ids = [r[0] for r in cur.fetchall()]
    print(f"inserted {len(project_ids)} projects")

    links, images, attachments = [], [], []
    for pid in project_ids:
        for tid in rng.sample(tag_ids, k=min(rng.randint(3, 6), len(tag_ids))):
            links.append((pid, tid, rng.random() < 0.3))
        for n in range(args.images):
            if args.image_files:
                path = f"stress/img-{rng.randrange(args.image_files):04d}.webp"
            else:
                path = None
            images.append((pid, rng.choice(IMAGE_LABELS), path, path, n))
        for n in range(args.attachments):
            if n % 2 == 0:
                attachments.append((pid, "document", rng.choice(DOC_NAMES),
                                    rng.choice(["PDF", "Markdown", "Spreadsheet"]),
                                    None, "#", n))
            else:
                attachments.append((pid, "download", rng.choice(DL_NAMES),
                                    rng.choice(["YAML", "HCL", "Shell", "JSON"]),
                                    f"{rng.randint(1, 900)} KB", "#", n))

    execute_values(cur,
        "INSERT INTO project_tags (project_id, tag_id, featured) VALUES %s "
        "ON CONFLICT DO NOTHING", links, page_size=1000)
    execute_values(cur,
        "INSERT INTO gallery_images (project_id, label, thumbnail_path, image_path, "
        "display_order) VALUES %s", images, page_size=1000)
    execute_values(cur,
        "INSERT INTO attachments (project_id, category, name, file_type, file_size, "
        "url, display_order) VALUES %s", attachments, page_size=1000)
    conn.commit()

    print(f"inserted {len(links)} tag links, {len(images)} gallery images, "
          f"{len(attachments)} attachments")


if __name__ == "__main__":
    main()
