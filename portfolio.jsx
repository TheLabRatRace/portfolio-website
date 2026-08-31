import { useState, useEffect, useRef } from "react";
import { Mail, Github, Linkedin, Image, FileText, Download, ChevronDown, ChevronUp, ExternalLink, Phone, MessageSquare, Calendar } from "lucide-react";

const SECTIONS = ["home", "about", "skills", "projects", "blog", "contact"];

const PROJECTS = [
  {
    title: "Self-Hosted AI Stack",
    tags: ["Proxmox", "Docker", "Ollama", "GPU Passthrough"],
    description:
      "Full AI inference platform on Proxmox with NVIDIA RTX GPU passthrough, running Ollama, Open WebUI, and vector search via Qdrant.",
    category: "infrastructure",
    details: {
      longDescription:
        "Designed and deployed a complete AI inference platform on a Proxmox VM with NVIDIA RTX 2000E Ada GPU passthrough. The stack runs via Docker Compose orchestrating Ollama for model inference, Open WebUI for the chat interface, Qdrant for vector search, and OpenClaw for multi-agent workflows. Models are managed through Docker bind mounts for persistence, with a curated lineup optimized for the available VRAM budget.",
      gallery: [
        { label: "Architecture Diagram", placeholder: true },
        { label: "Docker Compose Topology", placeholder: true },
      ],
      documents: [
        { name: "GPU Passthrough Setup Guide", type: "Markdown" },
        { name: "Model VRAM Budget Spreadsheet", type: "Spreadsheet" },
      ],
      downloads: [
        { name: "docker-compose.yml", type: "YAML", size: "3 KB" },
      ],
    },
  },
  {
    title: "Splunk CloudTrail Pipeline",
    tags: ["Splunk", "AWS", "S3", "SNS", "Security"],
    description:
      "End-to-end CloudTrail ingestion pipeline with S3, SNS triggers, and SPL-based IAM/security alerting dashboards.",
    category: "infrastructure",
    details: {
      longDescription:
        "Built an end-to-end CloudTrail log ingestion pipeline from AWS into Splunk. CloudTrail writes to S3, SNS notifications trigger ingestion, and SPL queries power dashboards for IAM activity monitoring, S3 access patterns, and security alerting. Debugged an S3 prefix mismatch that was silently breaking SNS notifications — a subtle issue that took careful log analysis to identify.",
      gallery: [
        { label: "Splunk Dashboard", placeholder: true },
        { label: "Pipeline Architecture", placeholder: true },
      ],
      documents: [
        { name: "SPL Query Library", type: "Markdown" },
        { name: "CloudTrail Ingestion Runbook", type: "PDF" },
      ],
      downloads: [],
    },
  },
  {
    title: "Network Monitoring Stack",
    tags: ["Grafana", "SNMP", "Cisco", "Palo Alto"],
    description:
      "SNMP-based monitoring for Cisco switches and Palo Alto firewalls using Grafana Alloy and Datadog integration.",
    category: "infrastructure",
    details: {
      longDescription:
        "Deployed SNMP-based monitoring across Cisco switches and Palo Alto firewalls using Grafana Alloy as the collection agent with Datadog as a secondary ingestion path. Built custom dashboards for bandwidth utilization, interface health, and firewall policy hits. The lab mirrors production so configs can be validated before rollout.",
      gallery: [
        { label: "Grafana Dashboard", placeholder: true },
        { label: "Network Topology", placeholder: true },
      ],
      documents: [
        { name: "SNMP OID Reference", type: "PDF" },
      ],
      downloads: [
        { name: "alloy-config.river", type: "Config", size: "2 KB" },
      ],
    },
  },
  {
    title: "Serverless API Pipeline",
    tags: ["API Gateway", "DynamoDB", "Lambda", "Python"],
    description:
      "Serverless data pipeline POC using AWS API Gateway, DynamoDB, and Python Lambda functions for email-to-database workflows.",
    category: "code",
    details: {
      longDescription:
        "Proof-of-concept serverless pipeline that receives inbound data via API Gateway, processes it through Python Lambda functions, and stores results in DynamoDB. Originally designed for an email-to-database workflow (email2airtable-poc), the pattern is reusable for any event-driven data ingestion. Includes IAM policy scoping, API key management, and CloudWatch monitoring.",
      gallery: [
        { label: "API Flow Diagram", placeholder: true },
      ],
      documents: [
        { name: "API Endpoint Documentation", type: "Markdown" },
        { name: "IAM Policy Reference", type: "PDF" },
      ],
      downloads: [
        { name: "lambda_handler.py", type: "Python", size: "2 KB" },
      ],
    },
  },
  {
    title: "GitLab CI/CD OIDC Migration",
    tags: ["GitLab", "IAM", "OIDC", "Terraform"],
    description:
      "Migrated CI/CD pipelines from static IAM keys to OIDC-based authentication for improved security posture.",
    category: "code",
    details: {
      longDescription:
        "Led the migration of GitLab CI/CD pipelines from static IAM access keys to OIDC-based federation. This eliminated long-lived credentials from the pipeline entirely — runners now assume short-lived IAM roles via OIDC trust policies. The migration included updating Terraform providers, scoping IAM policies to least privilege, and validating the trust chain across multiple AWS accounts.",
      gallery: [
        { label: "OIDC Auth Flow", placeholder: true },
      ],
      documents: [
        { name: "Migration Checklist", type: "PDF" },
        { name: "IAM Trust Policy Template", type: "JSON" },
      ],
      downloads: [
        { name: "gitlab-ci-oidc.yml", type: "YAML", size: "1 KB" },
      ],
    },
  },
  {
    title: "Discord AI Agent",
    tags: ["Python", "OpenClaw", "AWS Bedrock", "Discord"],
    description:
      "Multi-agent Discord bot orchestration powered by OpenClaw with AWS Bedrock backend for conversational AI.",
    category: "code",
    details: {
      longDescription:
        "Built a multi-agent Discord bot using OpenClaw for orchestration and AWS Bedrock for inference. The system supports multiple specialized agents that can be invoked contextually within Discord channels. Configuration includes IAM role scoping for Bedrock access, model ID routing (handling the us. vs global. prefix differences), and systemd service management for persistent uptime. Also deployed a secondary instance on a Raspberry Pi for testing.",
      gallery: [
        { label: "Bot Architecture", placeholder: true },
        { label: "Agent Flow Diagram", placeholder: true },
      ],
      documents: [
        { name: "Agent Configuration Guide", type: "Markdown" },
      ],
      downloads: [
        { name: "bot_config.py", type: "Python", size: "3 KB" },
      ],
    },
  },
];

const SKILLS = {
  "Cloud & Infrastructure": [
    "AWS (EC2, S3, RDS, IAM, SSM, Lambda, API Gateway)",
    "Proxmox / Virtualization",
    "Docker & Docker Compose",
    "Terraform / Terragrunt",
  ],
  "Monitoring & Security": [
    "Splunk (SPL, Universal Forwarders, TLS)",
    "Grafana / Datadog",
    "SNMP Monitoring",
    "CloudTrail / IAM Auditing",
  ],
  Networking: [
    "Cisco IOS (CCNA → CCNP track)",
    "Palo Alto Firewalls",
    "VLANs / Routing / Switching",
    "iSCSI / NFS Storage",
  ],
  Development: [
    "Python scripting & automation",
    "Java / Spring Boot / Tomcat",
    "Bash / Shell scripting",
    "Git / GitLab CI/CD",
  ],
};

/* ── Animated wrapper with entrance transition ── */
function FadeIn({ children, delay = 0, style: extraStyle = {} }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay * 1000);
    return () => clearTimeout(t);
  }, [delay]);
  return (
    <div
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(24px)",
        transition: "opacity 0.6s ease, transform 0.6s ease",
        ...extraStyle,
      }}
    >
      {children}
    </div>
  );
}

function TerminalLine({ children, prefix = "$", delay = 0 }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay * 1000);
    return () => clearTimeout(t);
  }, [delay]);
  return (
    <div
      style={{
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontSize: "1.3rem",
        color: "var(--term-text)",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateX(0)" : "translateX(-16px)",
        transition: "all 0.5s ease",
        marginBottom: "4px",
        letterSpacing: "0.02em",
      }}
    >
      <span style={{ color: "var(--accent)", marginRight: 8 }}>{prefix}</span>
      {children}
    </div>
  );
}

/* ── Project Card ── */
function ProjectCard({ project, index }) {
  const [hovered, setHovered] = useState(false);
  const catColor =
    project.category === "infrastructure" ? "var(--accent)" : "var(--accent2)";
  return (
    <FadeIn delay={index * 0.08} style={{ height: "100%" }}>
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          background: hovered
            ? "rgba(255,255,255,0.04)"
            : "rgba(255,255,255,0.015)",
          border: `1px solid ${hovered ? catColor : "rgba(255,255,255,0.06)"}`,
          borderRadius: 6,
          padding: "32px 28px",
          transition: "all 0.35s ease",
          cursor: "default",
          position: "relative",
          overflow: "hidden",
          height: "100%",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: hovered ? "100%" : "0%",
            height: 2,
            background: `linear-gradient(90deg, ${catColor}, transparent)`,
            transition: "width 0.5s ease",
          }}
        />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 12,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: catColor,
              boxShadow: `0 0 8px ${catColor}66`,
            }}
          />
          <h3
            style={{
              margin: 0,
              fontSize: "1.35rem",
              fontWeight: 600,
              fontFamily: "'Space Grotesk', 'DM Sans', sans-serif",
              color: "var(--heading)",
              letterSpacing: "-0.01em",
            }}
          >
            {project.title}
          </h3>
        </div>
        <p
          style={{
            margin: "0 0 16px",
            fontSize: "1.1rem",
            color: "var(--body-text)",
            lineHeight: 1.6,
            fontFamily: "'DM Sans', sans-serif",
            flex: 1,
          }}
        >
          {project.description}
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {project.tags.map((tag) => (
            <span
              key={tag}
              style={{
                padding: "4px 12px",
                fontSize: "1.15rem",
                fontFamily: "'JetBrains Mono', monospace",
                color: catColor,
                background: `${catColor}12`,
                border: `1px solid ${catColor}25`,
                borderRadius: 3,
                letterSpacing: "0.03em",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
    </FadeIn>
  );
}

/* ── Skill Group ── */
function SkillGroup({ title, items, index }) {
  return (
    <FadeIn delay={index * 0.1}>
      <div style={{ marginBottom: 32 }}>
        <h3
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "1rem",
            color: "var(--accent)",
            textTransform: "uppercase",
            letterSpacing: "0.12em",
            marginBottom: 14,
            fontWeight: 500,
          }}
        >
          {`// ${title}`}
        </h3>
        {items.map((item, i) => (
          <div
            key={i}
            style={{
              padding: "8px 0",
              fontSize: "1.1rem",
              color: "var(--body-text)",
              fontFamily: "'DM Sans', sans-serif",
              borderBottom: "1px solid rgba(255,255,255,0.04)",
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <span style={{ color: "var(--accent)", fontSize: "0.82rem" }}>
              ▸
            </span>
            {item}
          </div>
        ))}
      </div>
    </FadeIn>
  );
}

/* ── Section heading helper ── */
function SectionHeading({ children }) {
  return (
    <FadeIn>
      <h2
        style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: "2.8rem",
          fontWeight: 700,
          color: "var(--heading)",
          marginBottom: 8,
          letterSpacing: "-0.02em",
        }}
      >
        {children}
      </h2>
      <div
        style={{
          width: 48,
          height: 2,
          background: "linear-gradient(90deg, var(--accent), transparent)",
          marginBottom: 36,
        }}
      />
    </FadeIn>
  );
}

/* ══════════════════════════════════════════
   PAGE COMPONENTS — one per nav tab
   ══════════════════════════════════════════ */

function HomePage({ navigate }) {
  return (
    <div
      style={{
        minHeight: "calc(100vh - 64px)",
        display: "flex",
        alignItems: "center",
        padding: "60px 60px",
        maxWidth: 1080,
        margin: "0 auto",
      }}
    >
      <div>
        <FadeIn>
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "1.15rem",
              color: "var(--term-text)",
              marginBottom: 24,
              borderLeft: "2px solid var(--accent)",
              paddingLeft: 16,
            }}
          >
            <TerminalLine delay={0.2}>whoami</TerminalLine>
            <TerminalLine prefix="→" delay={0.5}>
              <span style={{ color: "var(--heading)" }}>Jeff Fredericks</span>
              {" — "}Technical Operations & Infrastructure Engineer
            </TerminalLine>
          </div>
        </FadeIn>

        <FadeIn delay={0.3}>
          <h1
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: "clamp(3rem, 6vw, 4.8rem)",
              fontWeight: 800,
              color: "var(--heading)",
              lineHeight: 1.1,
              margin: "0 0 24px",
              letterSpacing: "-0.03em",
            }}
          >
            Building systems{" "}
            <span style={{ color: "var(--accent)", fontStyle: "italic" }}>
              that scale
            </span>
            <br />& automation that{" "}
            <span style={{ color: "var(--accent2)", fontStyle: "italic" }}>
              endures
            </span>
          </h1>
        </FadeIn>

        <FadeIn delay={0.5}>
          <p
            style={{
              fontSize: "1.3rem",
              lineHeight: 1.7,
              maxWidth: 640,
              margin: "0 0 36px",
              color: "var(--body-text)",
            }}
          >
            Infrastructure engineer by trade. Python developer by practice.
            I design resilient systems, write clean automation, and make
            sure everything keeps running at scale.
          </p>
        </FadeIn>

        <FadeIn delay={0.7}>
          <div style={{ display: "flex", gap: 16 }}>
            <button
              onClick={() => navigate("projects")}
              style={{
                background: "var(--accent)",
                color: "#0a0b0f",
                border: "none",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "1rem",
                fontWeight: 600,
                padding: "14px 32px",
                borderRadius: 4,
                cursor: "pointer",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              View Projects
            </button>
            <button
              onClick={() => navigate("contact")}
              style={{
                background: "transparent",
                color: "var(--accent)",
                border: "1px solid rgba(201,168,76,0.3)",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "1rem",
                padding: "14px 32px",
                borderRadius: 4,
                cursor: "pointer",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              Get in Touch
            </button>
          </div>
        </FadeIn>
      </div>
    </div>
  );
}

function AboutPage() {
  return (
    <div style={{ padding: "80px 60px", maxWidth: 1080, margin: "0 auto" }}>
      <SectionHeading>About</SectionHeading>

      {/* Photo + Bio row */}
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 48, marginBottom: 48 }}>
        <FadeIn delay={0.1}>
          <div style={{ position: "relative" }}>
            {/* Photo frame with accent border */}
            <div
              style={{
                width: "100%",
                aspectRatio: "3 / 4",
                borderRadius: 8,
                overflow: "hidden",
                position: "relative",
                border: "1px solid rgba(201,168,76,0.2)",
                boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
              }}
            >
              {/* Placeholder — replace src with your photo */}
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  background: "linear-gradient(145deg, #1a1b22 0%, #12131a 50%, #1a1b22 100%)",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 12,
                }}
              >
                <span
                  style={{
                    fontFamily: "'Playfair Display', serif",
                    fontSize: "3.2rem",
                    fontWeight: 800,
                    color: "var(--accent)",
                    letterSpacing: "-0.02em",
                    opacity: 0.6,
                  }}
                >
                  JF
                </span>
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: "0.7rem",
                    color: "var(--term-text)",
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    opacity: 0.5,
                  }}
                >
                  your photo here
                </span>
              </div>
            </div>
            {/* Decorative accent corner */}
            <div
              style={{
                position: "absolute",
                bottom: -6,
                right: -6,
                width: 48,
                height: 48,
                borderRight: "2px solid var(--accent)",
                borderBottom: "2px solid var(--accent)",
                borderRadius: "0 0 8px 0",
                opacity: 0.4,
              }}
            />
          </div>
        </FadeIn>

        <FadeIn delay={0.2}>
          <p style={{ lineHeight: 1.8, fontSize: "1.2rem", marginTop: 0 }}>
            I work in technical operations for a television and streaming
            production company, managing infrastructure across AWS, on-prem
            networking, and monitoring platforms. My days involve Splunk
            pipelines, Cisco switches, and keeping production systems running
            smoothly.
          </p>
          <p style={{ lineHeight: 1.8, fontSize: "1.2rem", marginTop: 16 }}>
            Outside of work, I run a Proxmox homelab that's become a full R&D
            environment — from self-hosted AI inference to network monitoring
            experiments. I'm actively pursuing CCNA and CCNP Enterprise
            certifications.
          </p>
        </FadeIn>
      </div>

      {/* Terminal card — full width below */}
      <FadeIn delay={0.35}>
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid rgba(255,255,255,0.04)",
            borderRadius: 6,
            padding: "28px 32px",
          }}
        >
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "1.15rem",
              color: "var(--term-text)",
              marginBottom: 16,
            }}
          >
            {`/* current_status.py */`}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 48px" }}>
            <TerminalLine prefix="#" delay={0.1}>
              <span style={{ color: "var(--accent)" }}>Role:</span> Technical
              Operations Engineer
            </TerminalLine>
            <TerminalLine prefix="#" delay={0.15}>
              <span style={{ color: "var(--accent)" }}>Cloud:</span> AWS
              (EC2, S3, IAM, Lambda, RDS)
            </TerminalLine>
            <TerminalLine prefix="#" delay={0.2}>
              <span style={{ color: "var(--accent)" }}>Certs:</span> CCNA /
              CCNP (in progress)
            </TerminalLine>
            <TerminalLine prefix="#" delay={0.25}>
              <span style={{ color: "var(--accent)" }}>Stack:</span> Splunk ·
              Grafana · Docker · Terraform
            </TerminalLine>
            <TerminalLine prefix="#" delay={0.3}>
              <span style={{ color: "var(--accent)" }}>Languages:</span> Python,
              Java, Bash
            </TerminalLine>
            <TerminalLine prefix="#" delay={0.35}>
              <span style={{ color: "var(--accent)" }}>Networking:</span> Cisco
              IOS · Palo Alto
            </TerminalLine>
            <TerminalLine prefix="#" delay={0.4}>
              <span style={{ color: "var(--accent)" }}>Platforms:</span> Linux ·
              Proxmox · Windows
            </TerminalLine>
            <TerminalLine prefix="#" delay={0.45}>
              <span style={{ color: "var(--accent)" }}>CI/CD:</span> GitLab ·
              OIDC · Terragrunt
            </TerminalLine>
          </div>
        </div>
      </FadeIn>
    </div>
  );
}

function ProjectsPage() {
  const [subTab, setSubTab] = useState("work");
  const [filter, setFilter] = useState("all");
  const [expandedQuest, setExpandedQuest] = useState(null);
  const filtered =
    filter === "all" ? PROJECTS : PROJECTS.filter((p) => p.category === filter);

  const quests = [
    {
      title: "Proxmox Homelab",
      status: "active",
      description:
        "Full virtualization platform on a Minisforum MS-01 running multiple VMs and containers — the backbone of everything below.",
      specs: ["Intel 12th Gen", "64GB RAM", "ZFS Storage", "LVM Tiered"],
      details: {
        longDescription:
          "The Minisforum MS-01 serves as the foundation of my entire lab environment. Running Proxmox VE, it hosts a mix of Ubuntu and CentOS VMs alongside LXC containers. Storage is tiered across NVMe SSDs for high-performance workloads and a 5×4TB RAID-Z1 pool for bulk storage. The iGPU is disabled at BIOS level to enable clean PCIe passthrough of the NVIDIA RTX 2000E Ada to a dedicated AI workload VM.",
        gallery: [
          { label: "Proxmox Dashboard", placeholder: true },
          { label: "Hardware Setup", placeholder: true },
          { label: "Storage Layout", placeholder: true },
        ],
        documents: [
          { name: "Network Topology Diagram", type: "PDF" },
          { name: "VM Inventory & Resource Map", type: "Spreadsheet" },
        ],
        downloads: [
          { name: "Proxmox Post-Install Script", type: "Shell", size: "4 KB" },
        ],
      },
    },
    {
      title: "Self-Hosted AI Stack",
      status: "active",
      description:
        "GPU-accelerated AI inference with NVIDIA RTX 2000E Ada passthrough. Running Ollama, Open WebUI, Qdrant vector DB, and OpenClaw for multi-agent orchestration.",
      specs: ["RTX 2000E Ada", "Ollama", "Open WebUI", "Qdrant", "OpenClaw"],
      details: {
        longDescription:
          "The AI stack runs on a dedicated Ubuntu VM (ai01) with full GPU passthrough. Docker Compose orchestrates all services: Ollama handles model inference with a curated lineup (gpt-oss:20b, mistral-small3.2:24b, qwen3:14b, qwen3-coder:30b), Open WebUI provides the chat interface, Qdrant powers vector search, and OpenClaw enables multi-agent workflows with AWS Bedrock integration. Models are managed via Docker bind mounts for persistence across container rebuilds.",
        gallery: [
          { label: "Open WebUI Interface", placeholder: true },
          { label: "GPU Utilization Monitoring", placeholder: true },
          { label: "Docker Compose Architecture", placeholder: true },
        ],
        documents: [
          { name: "Model Lineup & VRAM Budget", type: "Markdown" },
          { name: "OpenClaw Agent Config Guide", type: "PDF" },
        ],
        downloads: [
          { name: "docker-compose.yml", type: "YAML", size: "3 KB" },
          { name: "ollama-model-pull.sh", type: "Shell", size: "1 KB" },
        ],
      },
    },
    {
      title: "Network Monitoring Lab",
      status: "active",
      description:
        "SNMP-based monitoring for Cisco switches and Palo Alto firewalls using Grafana Alloy and Datadog. Testing configs before deploying to production.",
      specs: ["Grafana Alloy", "SNMP", "Datadog", "Cisco IOS"],
      details: {
        longDescription:
          "This lab mirrors our production monitoring stack so I can test SNMP polling configs, dashboard layouts, and alerting rules before rolling them out. Grafana Alloy collects SNMP metrics from Cisco switches and Palo Alto firewalls, with Datadog as a secondary ingestion path for bandwidth and health monitoring. The goal is zero surprises when changes hit production.",
        gallery: [
          { label: "Grafana Dashboard", placeholder: true },
          { label: "SNMP Metric Explorer", placeholder: true },
        ],
        documents: [
          { name: "SNMP OID Reference Sheet", type: "PDF" },
        ],
        downloads: [
          { name: "alloy-config.river", type: "Config", size: "2 KB" },
        ],
      },
    },
    {
      title: "Docker Service Fleet",
      status: "active",
      description:
        "Self-hosted services via Docker Compose — Nextcloud, Wiki.js, Jellyfin, BookStack, PhotoPrism, Portainer, and more.",
      specs: ["Docker Compose", "Nginx Proxy", "PostgreSQL", "TLS"],
      details: {
        longDescription:
          "A growing fleet of self-hosted services, each in its own Docker Compose stack behind an Nginx reverse proxy with automated TLS certificates. PostgreSQL handles persistence for most services. The setup prioritizes data ownership and privacy — everything from file storage (Nextcloud) to documentation (Wiki.js, BookStack) to media (Jellyfin, PhotoPrism) runs locally.",
        gallery: [
          { label: "Portainer Overview", placeholder: true },
          { label: "Service Architecture", placeholder: true },
        ],
        documents: [
          { name: "Service Inventory", type: "Markdown" },
        ],
        downloads: [
          { name: "nginx-proxy-template.conf", type: "Config", size: "2 KB" },
        ],
      },
    },
    {
      title: "CCNA → CCNP Study Lab",
      status: "in progress",
      description:
        "Dedicated networking lab environment for hands-on certification prep. VLAN configs, routing protocols, and firewall rules in a safe sandbox.",
      specs: ["CCNA 200-301", "ENCOR 350-401", "ENAUTO 300-435"],
      details: {
        longDescription:
          "A sandboxed networking environment for CCNA and CCNP Enterprise certification prep. I configure VLANs, OSPF/EIGRP routing, ACLs, and firewall policies against real Cisco IOS images. The ENAUTO track adds Python-based network automation via RESTCONF/NETCONF. Study blocks are scheduled 8:00–9:30pm weeknights and Saturday mornings.",
        gallery: [
          { label: "Lab Topology", placeholder: true },
        ],
        documents: [
          { name: "Study Plan & Timeline", type: "PDF" },
          { name: "ENCOR Topic Checklist", type: "Spreadsheet" },
        ],
        downloads: [],
      },
    },
  ];

  const subTabs = [
    { label: "Work", value: "work" },
    { label: "Side Quests", value: "sidequests" },
  ];

  return (
    <div style={{ padding: "80px 60px", maxWidth: 1080, margin: "0 auto" }}>
      <SectionHeading>Projects</SectionHeading>

      {/* Sub-tab bar */}
      <FadeIn delay={0.05}>
        <div
          style={{
            display: "flex",
            gap: 0,
            marginBottom: 32,
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          {subTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => { setSubTab(tab.value); setFilter("all"); setExpandedQuest(null); }}
              style={{
                background: "transparent",
                border: "none",
                borderBottom: subTab === tab.value
                  ? "2px solid var(--accent)"
                  : "2px solid transparent",
                color: subTab === tab.value ? "var(--accent)" : "var(--term-text)",
                fontFamily: "'DM Sans', sans-serif",
                fontSize: "1.1rem",
                fontWeight: subTab === tab.value ? 600 : 400,
                padding: "12px 28px",
                cursor: "pointer",
                letterSpacing: "0.02em",
                transition: "all 0.25s ease",
                marginBottom: -1,
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </FadeIn>

      {/* Work sub-tab */}
      {subTab === "work" && (
        <>
          <FadeIn delay={0.1}>
            <div style={{ display: "flex", gap: 8, marginBottom: 32 }}>
              {[
                { label: "All", value: "all" },
                { label: "Infrastructure", value: "infrastructure" },
                { label: "Code", value: "code" },
              ].map((f) => (
                <button
                  key={f.value}
                  onClick={() => setFilter(f.value)}
                  style={{
                    background:
                      filter === f.value
                        ? "rgba(201,168,76,0.15)"
                        : "transparent",
                    border: `1px solid ${
                      filter === f.value
                        ? "var(--accent)"
                        : "rgba(255,255,255,0.06)"
                    }`,
                    color:
                      filter === f.value ? "var(--accent)" : "var(--term-text)",
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: "0.9rem",
                    padding: "8px 20px",
                    borderRadius: 3,
                    cursor: "pointer",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    transition: "all 0.25s ease",
                  }}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </FadeIn>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {filtered.map((project, i) => {
              const isSelected = expandedQuest === project.title;
              const catColor = project.category === "infrastructure" ? "var(--accent)" : "var(--accent2)";
              return (
              <FadeIn key={project.title} delay={0.1 + i * 0.06}>
                <div
                  onClick={() => setExpandedQuest(isSelected ? null : project.title)}
                  style={{
                    background: isSelected
                      ? "rgba(201,168,76,0.06)"
                      : "rgba(255,255,255,0.015)",
                    border: `1px solid ${
                      isSelected
                        ? "rgba(201,168,76,0.25)"
                        : "rgba(255,255,255,0.06)"
                    }`,
                    borderRadius: 6,
                    padding: "22px 28px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    cursor: "pointer",
                    transition: "all 0.25s ease",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.025)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.015)";
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}>
                    <span
                      style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: catColor,
                        boxShadow: `0 0 8px ${catColor}66`,
                        flexShrink: 0,
                      }}
                    />
                    <div style={{ minWidth: 0 }}>
                      <h3 style={{
                        margin: 0, fontSize: "1.2rem", fontWeight: 600,
                        fontFamily: "'DM Sans', sans-serif",
                        color: isSelected ? "var(--accent)" : "var(--heading)",
                        transition: "color 0.2s ease",
                      }}>{project.title}</h3>
                      <p style={{
                        margin: "4px 0 0", fontSize: "0.92rem",
                        color: "var(--body-text)", lineHeight: 1.5,
                      }}>{project.description}</p>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 14, flexShrink: 0, marginLeft: 20 }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "flex-end", maxWidth: 200 }}>
                      {project.tags.slice(0, 3).map((tag) => (
                        <span key={tag} style={{
                          padding: "3px 10px", fontSize: "0.72rem",
                          fontFamily: "'JetBrains Mono', monospace",
                          color: catColor,
                          background: `${catColor}12`,
                          border: `1px solid ${catColor}25`,
                          borderRadius: 3,
                        }}>{tag}</span>
                      ))}
                    </div>
                    <ExternalLink size={16} style={{ color: "var(--term-text)", flexShrink: 0 }} />
                  </div>
                </div>
              </FadeIn>
              );
            })}
          </div>
        </>
      )}

      {/* Side Quests sub-tab */}
      {subTab === "sidequests" && (
        <>
          <FadeIn delay={0.1}>
            <p
              style={{
                fontSize: "1.2rem",
                lineHeight: 1.7,
                color: "var(--body-text)",
                maxWidth: 700,
                marginBottom: 40,
              }}
            >
              The homelab is where I break things on purpose. It's a full R&D
              environment for testing infrastructure patterns, running AI workloads,
              and building skills that transfer directly to production.
            </p>
          </FadeIn>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {quests.map((quest, i) => {
              const isSelected = expandedQuest === quest.title;
              return (
              <FadeIn key={quest.title} delay={0.15 + i * 0.08}>
                <div
                  onClick={() =>
                    setExpandedQuest(isSelected ? null : quest.title)
                  }
                  style={{
                    background: isSelected
                      ? "rgba(201,168,76,0.06)"
                      : "rgba(255,255,255,0.015)",
                    border: `1px solid ${
                      isSelected
                        ? "rgba(201,168,76,0.25)"
                        : "rgba(255,255,255,0.06)"
                    }`,
                    borderRadius: 6,
                    padding: "20px 28px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    cursor: "pointer",
                    transition: "all 0.25s ease",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.025)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.015)";
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background:
                          quest.status === "active" ? "#4ade80" : "var(--accent)",
                        boxShadow:
                          quest.status === "active"
                            ? "0 0 8px rgba(74,222,128,0.4)"
                            : "0 0 8px rgba(201,168,76,0.4)",
                      }}
                    />
                    <h3
                      style={{
                        margin: 0,
                        fontSize: "1.2rem",
                        fontWeight: 600,
                        fontFamily: "'DM Sans', sans-serif",
                        color: isSelected ? "var(--accent)" : "var(--heading)",
                        transition: "color 0.2s ease",
                      }}
                    >
                      {quest.title}
                    </h3>
                    <span
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: "0.72rem",
                        color: quest.status === "active" ? "#4ade80" : "var(--accent)",
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        opacity: 0.7,
                      }}
                    >
                      {quest.status === "active" ? "● live" : "● in progress"}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "flex-end" }}>
                      {quest.specs.slice(0, 3).map((spec) => (
                        <span
                          key={spec}
                          style={{
                            padding: "3px 10px",
                            fontSize: "0.72rem",
                            fontFamily: "'JetBrains Mono', monospace",
                            color: "var(--accent2)",
                            background: "rgba(91,155,213,0.08)",
                            border: "1px solid rgba(91,155,213,0.15)",
                            borderRadius: 3,
                          }}
                        >
                          {spec}
                        </span>
                      ))}
                    </div>
                    <ExternalLink size={16} style={{ color: "var(--term-text)", flexShrink: 0 }} />
                  </div>
                </div>
              </FadeIn>
              );
            })}
          </div>

        </>
      )}

      {/* Shared side panel overlay — works for both Work and Side Quests */}
      {expandedQuest && (() => {
        const allItems = [...PROJECTS, ...quests];
        const quest = allItems.find((q) => q.title === expandedQuest);
        if (!quest?.details) return null;
        return (
          <>
            {/* Backdrop */}
            <div
              onClick={() => setExpandedQuest(null)}
              style={{
                position: "fixed",
                inset: 0,
                background: "rgba(0,0,0,0.5)",
                zIndex: 200,
                animation: "fadeIn 0.25s ease both",
              }}
            />
                {/* Panel */}
                <div
                  style={{
                    position: "fixed",
                    top: 0,
                    right: 0,
                    bottom: 0,
                    width: "min(560px, 85vw)",
                    background: "#12131a",
                    borderLeft: "1px solid rgba(201,168,76,0.15)",
                    zIndex: 201,
                    overflowY: "auto",
                    animation: "slideIn 0.35s ease both",
                    boxShadow: "-8px 0 32px rgba(0,0,0,0.4)",
                  }}
                >
                  {/* Panel header */}
                  <div
                    style={{
                      position: "sticky",
                      top: 0,
                      background: "#12131a",
                      borderBottom: "1px solid rgba(255,255,255,0.06)",
                      padding: "20px 32px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      zIndex: 1,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          background: quest.status
                            ? (quest.status === "active" ? "#4ade80" : "var(--accent)")
                            : (quest.category === "code" ? "var(--accent2)" : "var(--accent)"),
                          boxShadow: quest.status
                            ? (quest.status === "active"
                              ? "0 0 8px rgba(74,222,128,0.4)"
                              : "0 0 8px rgba(201,168,76,0.4)")
                            : (quest.category === "code"
                              ? "0 0 8px rgba(91,155,213,0.4)"
                              : "0 0 8px rgba(201,168,76,0.4)"),
                        }}
                      />
                      <h2
                        style={{
                          margin: 0,
                          fontSize: "1.4rem",
                          fontWeight: 700,
                          fontFamily: "'Playfair Display', serif",
                          color: "var(--heading)",
                        }}
                      >
                        {quest.title}
                      </h2>
                    </div>
                    <button
                      onClick={() => setExpandedQuest(null)}
                      style={{
                        background: "transparent",
                        border: "1px solid rgba(255,255,255,0.08)",
                        color: "var(--term-text)",
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: "0.78rem",
                        padding: "6px 14px",
                        borderRadius: 4,
                        cursor: "pointer",
                        transition: "all 0.2s ease",
                      }}
                    >
                      ✕ Close
                    </button>
                  </div>

                  {/* Panel content */}
                  <div style={{ padding: "32px" }}>
                    {/* Tags / Specs */}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 24 }}>
                      {(quest.specs || quest.tags || []).map((spec) => (
                        <span
                          key={spec}
                          style={{
                            padding: "4px 12px",
                            fontSize: "0.78rem",
                            fontFamily: "'JetBrains Mono', monospace",
                            color: "var(--accent2)",
                            background: "rgba(91,155,213,0.08)",
                            border: "1px solid rgba(91,155,213,0.15)",
                            borderRadius: 3,
                          }}
                        >
                          {spec}
                        </span>
                      ))}
                    </div>

                    {/* Long description */}
                    <p style={{
                      fontSize: "1.05rem",
                      lineHeight: 1.7,
                      color: "var(--body-text)",
                      margin: "0 0 36px",
                    }}>
                      {quest.details.longDescription}
                    </p>

                    {/* Gallery */}
                    {quest.details.gallery?.length > 0 && (
                      <div style={{ marginBottom: 32 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                          <Image size={16} style={{ color: "var(--accent)" }} />
                          <span style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: "0.78rem",
                            color: "var(--accent)",
                            textTransform: "uppercase",
                            letterSpacing: "0.08em",
                          }}>Gallery</span>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                          {quest.details.gallery.map((img) => (
                            <div
                              key={img.label}
                              style={{
                                background: "rgba(255,255,255,0.02)",
                                border: "1px solid rgba(255,255,255,0.04)",
                                borderRadius: 4,
                                padding: "24px 16px",
                                textAlign: "center",
                                cursor: "pointer",
                                transition: "border-color 0.2s ease",
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.borderColor = "rgba(201,168,76,0.2)"}
                              onMouseLeave={(e) => e.currentTarget.style.borderColor = "rgba(255,255,255,0.04)"}
                            >
                              <Image size={24} style={{ color: "var(--term-text)", marginBottom: 8 }} />
                              <div style={{ fontSize: "0.85rem", color: "var(--heading)" }}>{img.label}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Documents */}
                    {quest.details.documents?.length > 0 && (
                      <div style={{ marginBottom: 32 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                          <FileText size={16} style={{ color: "var(--accent)" }} />
                          <span style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: "0.78rem",
                            color: "var(--accent)",
                            textTransform: "uppercase",
                            letterSpacing: "0.08em",
                          }}>Documents</span>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {quest.details.documents.map((doc) => (
                            <div
                              key={doc.name}
                              style={{
                                background: "rgba(255,255,255,0.02)",
                                border: "1px solid rgba(255,255,255,0.04)",
                                borderRadius: 4,
                                padding: "14px 16px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                cursor: "pointer",
                                transition: "border-color 0.2s ease",
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.borderColor = "rgba(201,168,76,0.2)"}
                              onMouseLeave={(e) => e.currentTarget.style.borderColor = "rgba(255,255,255,0.04)"}
                            >
                              <div>
                                <div style={{ fontSize: "0.92rem", color: "var(--heading)", marginBottom: 2 }}>{doc.name}</div>
                                <div style={{ fontSize: "0.72rem", fontFamily: "'JetBrains Mono', monospace", color: "var(--term-text)", textTransform: "uppercase" }}>{doc.type}</div>
                              </div>
                              <ExternalLink size={14} style={{ color: "var(--term-text)" }} />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Downloads */}
                    {quest.details.downloads?.length > 0 && (
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                          <Download size={16} style={{ color: "var(--accent)" }} />
                          <span style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: "0.78rem",
                            color: "var(--accent)",
                            textTransform: "uppercase",
                            letterSpacing: "0.08em",
                          }}>Downloads</span>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {quest.details.downloads.map((dl) => (
                            <div
                              key={dl.name}
                              style={{
                                background: "rgba(255,255,255,0.02)",
                                border: "1px solid rgba(255,255,255,0.04)",
                                borderRadius: 4,
                                padding: "14px 16px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                cursor: "pointer",
                                transition: "border-color 0.2s ease",
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.borderColor = "rgba(201,168,76,0.2)"}
                              onMouseLeave={(e) => e.currentTarget.style.borderColor = "rgba(255,255,255,0.04)"}
                            >
                              <div>
                                <div style={{ fontSize: "0.92rem", color: "var(--heading)", marginBottom: 2 }}>{dl.name}</div>
                                <div style={{ fontSize: "0.72rem", fontFamily: "'JetBrains Mono', monospace", color: "var(--term-text)" }}>{dl.type} · {dl.size}</div>
                              </div>
                              <Download size={14} style={{ color: "var(--accent2)" }} />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </>
            );
          })()}
    </div>
  );
}

function SkillsPage() {
  return (
    <div style={{ padding: "80px 60px", maxWidth: 1080, margin: "0 auto" }}>
      <SectionHeading>Skills</SectionHeading>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "16px 48px",
        }}
      >
        {Object.entries(SKILLS).map(([title, items], i) => (
          <SkillGroup key={title} title={title} items={items} index={i} />
        ))}
      </div>
    </div>
  );
}

function BlogPage() {
  const [selectedPost, setSelectedPost] = useState(null);

  const posts = [
    {
      title: "GPU Passthrough on Proxmox: What I Wish I Knew",
      date: "2026-04-28",
      tags: ["Proxmox", "GPU", "Homelab"],
      excerpt:
        "Getting NVIDIA RTX passthrough working on a Minisforum MS-01 wasn't plug-and-play. Here's every BIOS setting, kernel parameter, and gotcha I hit along the way.",
      content:
        "This is a placeholder for the full blog post. Replace this with your actual content — markdown rendering, rich text, or even a fetch from a CMS or static files.",
    },
    {
      title: "Debugging a Silent Failure: S3 Prefix Mismatches in Splunk Ingestion",
      date: "2026-04-14",
      tags: ["Splunk", "AWS", "CloudTrail"],
      excerpt:
        "Our CloudTrail logs just stopped showing up in Splunk. No errors, no alerts. The root cause was a one-character S3 prefix mismatch that broke SNS notifications.",
      content:
        "This is a placeholder for the full blog post. Replace this with your actual content.",
    },
    {
      title: "From Static Keys to OIDC: Securing GitLab CI/CD on AWS",
      date: "2026-03-22",
      tags: ["GitLab", "OIDC", "IAM", "Security"],
      excerpt:
        "Static IAM keys in CI/CD pipelines are a liability. Here's how I migrated our GitLab runners to OIDC federation — and why it's worth the effort.",
      content:
        "This is a placeholder for the full blog post. Replace this with your actual content.",
    },
    {
      title: "Building a Python Automation Toolkit for Infrastructure",
      date: "2026-03-08",
      tags: ["Python", "Automation", "AWS"],
      excerpt:
        "A collection of Python scripts I use daily — from EC2 inventory snapshots to Splunk forwarder health checks. Nothing fancy, just reliable.",
      content:
        "This is a placeholder for the full blog post. Replace this with your actual content.",
    },
    {
      title: "Self-Hosting AI: Running Ollama at Home vs. Paying for APIs",
      date: "2026-02-19",
      tags: ["AI", "Ollama", "Homelab", "Cost"],
      excerpt:
        "I run my own AI inference stack on a single GPU. Here's a real cost comparison against API pricing, plus the intangibles you can't put a dollar amount on.",
      content:
        "This is a placeholder for the full blog post. Replace this with your actual content.",
    },
  ];

  const formatDate = (dateStr) => {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  };

  // Full post view
  if (selectedPost) {
    const post = posts.find((p) => p.title === selectedPost);
    if (!post) return null;
    return (
      <div style={{ padding: "80px 60px", maxWidth: 1080, margin: "0 auto", animation: "pageIn 0.4s ease both" }}>
        <FadeIn>
          <button
            onClick={() => setSelectedPost(null)}
            style={{
              display: "flex", alignItems: "center", gap: 8,
              background: "transparent", border: "none",
              color: "var(--accent)",
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "0.9rem", padding: "0 0 32px",
              cursor: "pointer", letterSpacing: "0.04em",
            }}
          >
            ← Back to Blog
          </button>
        </FadeIn>

        <FadeIn delay={0.1}>
          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "0.82rem", color: "var(--term-text)",
            marginBottom: 12, letterSpacing: "0.04em",
          }}>
            {formatDate(post.date)}
          </div>
          <h1 style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: "2.4rem", fontWeight: 700,
            color: "var(--heading)", margin: "0 0 20px",
            letterSpacing: "-0.02em", lineHeight: 1.2,
          }}>
            {post.title}
          </h1>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 40 }}>
            {post.tags.map((tag) => (
              <span key={tag} style={{
                padding: "4px 14px", fontSize: "0.78rem",
                fontFamily: "'JetBrains Mono', monospace",
                color: "var(--accent2)",
                background: "rgba(91,155,213,0.08)",
                border: "1px solid rgba(91,155,213,0.15)",
                borderRadius: 4,
              }}>{tag}</span>
            ))}
          </div>
        </FadeIn>

        <FadeIn delay={0.2}>
          <div style={{
            background: "var(--surface)",
            border: "1px solid rgba(255,255,255,0.04)",
            borderRadius: 6, padding: "40px 40px",
          }}>
            <p style={{
              fontSize: "1.15rem", lineHeight: 1.8,
              color: "var(--body-text)", margin: 0,
              fontStyle: "italic",
            }}>
              {post.excerpt}
            </p>
            <div style={{
              borderTop: "1px solid rgba(255,255,255,0.06)",
              marginTop: 28, paddingTop: 28,
            }}>
              <p style={{
                fontSize: "1.1rem", lineHeight: 1.8,
                color: "var(--body-text)", margin: 0,
              }}>
                {post.content}
              </p>
            </div>
          </div>
        </FadeIn>
      </div>
    );
  }

  // Blog listing view
  return (
    <div style={{ padding: "80px 60px", maxWidth: 1080, margin: "0 auto" }}>
      <SectionHeading>Blog</SectionHeading>

      <FadeIn delay={0.1}>
        <p style={{
          fontSize: "1.2rem", lineHeight: 1.7,
          color: "var(--body-text)", maxWidth: 700,
          marginBottom: 40,
        }}>
          Notes from the field — infrastructure war stories, homelab experiments,
          and things I learned the hard way.
        </p>
      </FadeIn>

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {posts.map((post, i) => (
          <FadeIn key={post.title} delay={0.12 + i * 0.06}>
            <div
              onClick={() => setSelectedPost(post.title)}
              style={{
                background: "rgba(255,255,255,0.015)",
                border: "1px solid rgba(255,255,255,0.06)",
                borderRadius: 6,
                padding: "36px 40px",
                cursor: "pointer",
                transition: "all 0.25s ease",
                display: "flex",
                flexDirection: "column",
                gap: 20,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.03)";
                e.currentTarget.style.borderColor = "rgba(201,168,76,0.2)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.015)";
                e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)";
              }}
            >
              {/* Title + tags row */}
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: 24,
              }}>
                <h3 style={{
                  margin: 0, fontSize: "1.3rem", fontWeight: 600,
                  fontFamily: "'DM Sans', sans-serif", color: "var(--heading)",
                  lineHeight: 1.35,
                }}>
                  {post.title}
                </h3>
                <div style={{
                  display: "flex", flexWrap: "wrap", gap: 6,
                  justifyContent: "flex-end", maxWidth: 200,
                  flexShrink: 0,
                }}>
                  {post.tags.slice(0, 3).map((tag) => (
                    <span key={tag} style={{
                      padding: "3px 10px", fontSize: "0.72rem",
                      fontFamily: "'JetBrains Mono', monospace",
                      color: "var(--accent2)",
                      background: "rgba(91,155,213,0.08)",
                      border: "1px solid rgba(91,155,213,0.15)",
                      borderRadius: 3,
                    }}>{tag}</span>
                  ))}
                </div>
              </div>

              {/* Excerpt */}
              <p style={{
                margin: 0, fontSize: "1.05rem",
                color: "var(--body-text)", lineHeight: 1.7,
                maxWidth: 820,
              }}>
                {post.excerpt}
              </p>

              {/* Date + read more row */}
              <div style={{
                display: "flex",
                justifyContent: "flex-end",
                alignItems: "center",
                gap: 16,
                paddingTop: 4,
              }}>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: "0.8rem",
                  color: "var(--accent)",
                  letterSpacing: "0.04em",
                  opacity: 0.8,
                }}>
                  {formatDate(post.date)}
                </span>
              </div>
            </div>
          </FadeIn>
        ))}
      </div>
    </div>
  );
}

function ContactPage() {
  return (
    <div style={{ padding: "80px 60px", maxWidth: 1080, margin: "0 auto" }}>
      <SectionHeading>Get In Touch</SectionHeading>

      <FadeIn delay={0.15}>
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid rgba(255,255,255,0.04)",
            borderRadius: 6,
            padding: "40px 40px",
          }}
        >
          <p
            style={{
              lineHeight: 1.7,
              marginBottom: 28,
              fontSize: "1.2rem",
            }}
          >
            Whether it's infrastructure consulting, a Python project, or just
            talking shop about homelabs — I'd like to hear from you.
          </p>
          <div
            style={{ display: "flex", flexDirection: "column", gap: 16 }}
          >
            {[
              {
                label: "Email",
                value: "your.email@example.com",
                Icon: Mail,
                href: "mailto:your.email@example.com",
              },
              {
                label: "Phone",
                value: "(555) 123-4567",
                Icon: Phone,
                href: "tel:+15551234567",
              },
              {
                label: "GitHub",
                value: "github.com/yourusername",
                Icon: Github,
                href: "https://github.com/yourusername",
              },
              {
                label: "LinkedIn",
                value: "linkedin.com/in/yourprofile",
                Icon: Linkedin,
                href: "https://linkedin.com/in/yourprofile",
              },
              {
                label: "Discord",
                value: "yourhandle",
                Icon: MessageSquare,
              },
              {
                label: "Schedule",
                value: "Coming soon",
                Icon: Calendar,
                disabled: true,
              },
            ].map((link) => (
              <a
                key={link.label}
                href={link.href || undefined}
                target={link.href && !link.href.startsWith("mailto:") && !link.href.startsWith("tel:") ? "_blank" : undefined}
                rel={link.href && !link.href.startsWith("mailto:") && !link.href.startsWith("tel:") ? "noopener noreferrer" : undefined}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                  padding: "14px 16px",
                  borderBottom: "1px solid rgba(255,255,255,0.03)",
                  borderRadius: 4,
                  cursor: link.disabled ? "default" : "pointer",
                  transition: "background 0.2s ease",
                  textDecoration: "none",
                  opacity: link.disabled ? 0.45 : 1,
                }}
                onMouseEnter={(e) => { if (!link.disabled) e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <link.Icon
                  size={20}
                  style={{ color: "var(--accent)", flexShrink: 0 }}
                />
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: "0.9rem",
                    color: "var(--term-text)",
                    minWidth: 120,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    flexShrink: 0,
                  }}
                >
                  {link.label}
                </span>
                <span
                  style={{ color: link.disabled ? "var(--term-text)" : "var(--heading)", fontSize: "1.1rem" }}
                >
                  {link.value}
                </span>
              </a>
            ))}
          </div>
        </div>
      </FadeIn>

      <FadeIn delay={0.3}>
        <div style={{
          marginTop: 32,
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}>
          <button
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              background: "var(--accent)",
              color: "#0a0b0f",
              border: "none",
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "0.9rem",
              fontWeight: 600,
              padding: "14px 28px",
              borderRadius: 4,
              cursor: "pointer",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
            }}
          >
            <Download size={16} />
            Download Resume
          </button>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "0.78rem",
            color: "var(--term-text)",
            letterSpacing: "0.04em",
          }}>
            PDF · Updated 2026
          </span>
        </div>
      </FadeIn>
    </div>
  );
}

/* ══════════════════════════════════════════
   MAIN PORTFOLIO COMPONENT
   ══════════════════════════════════════════ */

export default function Portfolio() {
  const [activeSection, setActiveSection] = useState("home");
  const [fadeKey, setFadeKey] = useState(0);

  useEffect(() => {
    const link = document.createElement("link");
    link.href =
      "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Playfair+Display:wght@700;800&display=swap";
    link.rel = "stylesheet";
    document.head.appendChild(link);
  }, []);

  const navigate = (section) => {
    setActiveSection(section);
    setFadeKey((k) => k + 1);
  };

  const renderPage = () => {
    switch (activeSection) {
      case "home":
        return <HomePage navigate={navigate} />;
      case "about":
        return <AboutPage />;
      case "projects":
        return <ProjectsPage />;
      case "skills":
        return <SkillsPage />;
      case "blog":
        return <BlogPage />;
      case "contact":
        return <ContactPage />;
      default:
        return <HomePage navigate={navigate} />;
    }
  };

  return (
    <div
      style={{
        "--bg": "#0a0b0f",
        "--surface": "#12131a",
        "--heading": "#e8e6e1",
        "--body-text": "#9a978f",
        "--accent": "#c9a84c",
        "--accent2": "#5b9bd5",
        "--term-text": "#7a7770",
        "--nav-bg": "rgba(10,11,15,0.92)",
        fontFamily: "'DM Sans', sans-serif",
        background: "var(--bg)",
        color: "var(--body-text)",
        height: "100vh",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Subtle grid texture */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.015) 1px, transparent 0)",
          backgroundSize: "48px 48px",
        }}
      />

      {/* Ambient glow */}
      <div
        style={{
          position: "fixed",
          top: -200,
          right: -200,
          width: 600,
          height: 600,
          background:
            "radial-gradient(circle, rgba(201,168,76,0.04) 0%, transparent 70%)",
          zIndex: 0,
          pointerEvents: "none",
        }}
      />

      {/* Navigation */}
      <nav
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          background: "var(--nav-bg)",
          backdropFilter: "blur(16px)",
          borderBottom: "1px solid rgba(255,255,255,0.04)",
          padding: "0 40px",
          height: 64,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            fontFamily: "'Playfair Display', serif",
            fontWeight: 800,
            fontSize: "1.5rem",
            color: "var(--heading)",
            letterSpacing: "-0.02em",
            cursor: "pointer",
          }}
          onClick={() => navigate("home")}
        >
          <span style={{ color: "var(--accent)" }}>Jeff</span>
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "0.82rem",
              color: "var(--term-text)",
              marginLeft: 10,
              fontWeight: 400,
            }}
          >
            // ops · code · automate
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {SECTIONS.map((s) => (
            <button
              key={s}
              onClick={() => navigate(s)}
              style={{
                background:
                  activeSection === s
                    ? "rgba(201,168,76,0.12)"
                    : "transparent",
                border: "none",
                color:
                  activeSection === s ? "var(--accent)" : "var(--term-text)",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "1.15rem",
                padding: "8px 14px",
                borderRadius: 4,
                cursor: "pointer",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                transition: "all 0.25s ease",
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </nav>

      {/* Page content — only one section visible at a time */}
      <div
        key={fadeKey}
        style={{
          height: "100vh",
          overflowY: "auto",
          paddingTop: 64,
          position: "relative",
          zIndex: 1,
          animation: "pageIn 0.4s ease both",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ flex: 1 }}>
          {renderPage()}
        </div>

        {/* Footer */}
        <footer
          style={{
            padding: "32px 60px",
            borderTop: "1px solid rgba(255,255,255,0.04)",
            textAlign: "center",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "0.85rem",
            color: "var(--term-text)",
            letterSpacing: "0.06em",
          }}
        >
          Built with intention · © 2026
        </footer>
      </div>

      {/* Page transition animation */}
      <style>{`
        @keyframes pageIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes detailIn {
          from { opacity: 0; max-height: 0; }
          to   { opacity: 1; max-height: 1200px; }
        }
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to   { transform: translateX(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
