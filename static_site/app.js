/* The static shell's router and views.
 *
 * Everything here reads from /api/v1 and writes into #view. The markup is
 * copied from the Jinja templates rather than invented, because the
 * stylesheet is the same file: a class this script makes up gets no styling
 * at all, and the failure mode is a page that renders and looks wrong. Where
 * you see an odd wrapper div, it is there because style.css hangs the page
 * padding off it.
 *
 * No framework and no build step. One file at the edge, five page types.
 */
(function () {
  "use strict";

  var API = (window.SITE && window.SITE.apiBase) || "/api/v1";
  var view = document.getElementById("view");

  // ── helpers ───────────────────────────────────────────────────────────────

  /* Every string from the API goes through this before it reaches innerHTML.
   * The content is ours, but "ours" means a database an admin types into, and
   * one unescaped angle bracket in a project description is a script tag. */
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function get(path) {
    return fetch(API + path, { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) {
          var error = new Error("HTTP " + response.status);
          error.status = response.status;
          throw error;
        }
        return response.json();
      });
  }

  function render(html) {
    listKey = null;
    view.innerHTML = html;
    view.setAttribute("aria-busy", "false");
    /* <main> is the scroller, not the window -- style.css gives it height:100dvh
     * and overflow-y:auto, so window.scrollTo alone does nothing and a view
     * navigated to from halfway down a long page opens halfway down. That also
     * strands the reveal below: anything already above the viewport never
     * intersects, so it never gets .visible and stays invisible for good. */
    var scroller = document.querySelector("main");
    if (scroller) scroller.scrollTop = 0;
    window.scrollTo(0, 0);
    reveal();
  }

  /* .fade-in and .terminal-line are both opacity:0 in style.css and wait for a
   * .visible class. The rendered site adds it from app/static/js/main.js, which
   * this shell does not load -- so without this the home page's terminal block
   * is a gold rule with nothing beside it: the markup is there, the text never
   * appears. Same failure for the status card and every fade-in wrapper.
   *
   * The reveal is main.js's, kept deliberately identical: staggered by position
   * within the batch that came into view, capped so nothing waits long. The
   * observer is rebuilt per render rather than created once, because every view
   * replaces the elements it was watching. */
  var REVEAL_STEP = 0.04;  // seconds between neighbours
  var REVEAL_CAP = 0.2;    // longest any one element waits

  function reveal() {
    var animated = view.querySelectorAll(".fade-in, .terminal-line");
    if (!animated.length) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
        !("IntersectionObserver" in window)) {
      animated.forEach(function (el) { el.classList.add("visible"); });
      return;
    }

    var observer = new IntersectionObserver(function (entries, obs) {
      entries
        .filter(function (entry) { return entry.isIntersecting; })
        .sort(function (a, b) {
          return a.boundingClientRect.top - b.boundingClientRect.top;
        })
        .forEach(function (entry, i) {
          entry.target.style.transitionDelay =
            Math.min(i * REVEAL_STEP, REVEAL_CAP) + "s";
          entry.target.classList.add("visible");
          obs.unobserve(entry.target);
        });
    }, { rootMargin: "120px 0px 160px 0px", threshold: 0.01 });

    animated.forEach(function (el) { observer.observe(el); });
  }

  function loading() {
    view.setAttribute("aria-busy", "true");
    view.innerHTML = '<div class="projects-page"><p class="blog-intro">Loading…</p></div>';
  }

  /* The same markup errors/404.html and errors/500.html render, because
   * .error-page is centred and the section heading's underline bar is not --
   * borrowing the heading here leaves an orphaned gold dash floating to the
   * left of the title. The status is real: a 404 from the API means the slug
   * does not exist, and anything else means the API did not answer. */
  function failed(error) {
    var missing = error && error.status === 404;
    render(
      '<div class="error-page">' +
      '<div class="error-code">' + (missing ? "404" : "500") + "</div>" +
      '<h1 class="error-title">' +
      (missing ? "Page not found" : "Server error") +
      "</h1>" +
      '<p class="error-body">' +
      (missing
        ? "That path doesn't exist."
        : "The content service didn't answer. Try again in a moment.") +
      "</p>" +
      '<a href="/" class="btn-primary" data-link>Go home</a></div>'
    );
  }

  function heading(text, extra) {
    return '<div class="section-heading' + (extra ? " " + extra : "") + '"><h2>' +
      esc(text) + '</h2><div class="section-heading-bar"></div></div>';
  }

  function chips(list, className, limit) {
    return (list || []).slice(0, limit || 3).map(function (name) {
      return '<span class="' + className + '">' + esc(name) + "</span>";
    }).join("");
  }

  function count(total, noun) {
    return '<span class="result-count">' + total + " " + noun +
      (total === 1 ? "" : "s") + "</span>";
  }

  /* Dates arrive as ISO strings and the rendered site shows "12 Mar 2026".
   * Built from UTC parts rather than toLocaleDateString: a date-only value
   * parses as midnight UTC, and in any timezone west of London the local
   * rendering of that is the day before. */
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function formatDate(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d)) return "";
    return d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear();
  }

  /* The lucide-shaped icons the templates draw inline. Same 24-unit viewBox and
   * the same stroke settings everywhere, so only the paths and the size differ. */
  function icon(paths, size, className) {
    return '<svg' + (className ? ' class="' + className + '"' : "") +
      ' xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '"' +
      ' viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      paths + "</svg>";
  }

  var EXT_PATHS =
    '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>' +
    '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>';

  var DOWNLOAD_PATHS =
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
    '<polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>';

  var GALLERY_PATHS =
    '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/>' +
    '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>';

  var DOCUMENT_PATHS =
    '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>' +
    '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/>' +
    '<path d="M16 17H8"/>';

  var EXT_ICON = icon(EXT_PATHS, 16, "ext-link-icon");

  var IMAGE_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"' +
    ' fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"' +
    ' stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="3"' +
    ' rx="2" ry="2"/><circle cx="9" cy="9" r="2"/>' +
    '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>';

  /* The API reports `pages`, so the control is arithmetic rather than a second
   * request. The links are real hrefs -- the router intercepts a plain click
   * and a middle-click still opens a tab. */
  function pager(data, href) {
    if (data.pages <= 1) return "";
    var page = data.page, out = ['<nav class="pagination" aria-label="Pagination">'];

    out.push(page > 1
      ? '<a class="page-btn page-btn--step" rel="prev" href="' + href(page - 1) +
        '" data-link aria-label="Previous page"><span class="page-arrow">&larr;</span>' +
        '<span class="page-word">Prev</span></a>'
      : '<span class="page-btn page-btn--step disabled" aria-disabled="true"' +
        ' aria-label="Previous page"><span class="page-arrow">&larr;</span>' +
        '<span class="page-word">Prev</span></span>');

    for (var n = 1; n <= data.pages; n++) {
      out.push(n === page
        ? '<span class="page-btn active" aria-current="page">' + n + "</span>"
        : '<a class="page-btn" href="' + href(n) + '" data-link>' + n + "</a>");
    }

    out.push('<span class="page-pos">' + page + " / " + data.pages + "</span>");

    out.push(page < data.pages
      ? '<a class="page-btn page-btn--step" rel="next" href="' + href(page + 1) +
        '" data-link aria-label="Next page"><span class="page-word">Next</span>' +
        '<span class="page-arrow">&rarr;</span></a>'
      : '<span class="page-btn page-btn--step disabled" aria-disabled="true"' +
        ' aria-label="Next page"><span class="page-word">Next</span>' +
        '<span class="page-arrow">&rarr;</span></span>');

    out.push('<span class="page-count">' + data.total + " total</span></nav>");
    return out.join("");
  }

  // ── rows ──────────────────────────────────────────────────────────────────

  function projectRow(project) {
    return (
      '<div class="project-row-wrap" data-category="' + esc(project.category) + '">' +
      '<a class="project-row cat-' + esc(project.category) + '" data-link href="/projects/' +
      encodeURIComponent(project.slug) + '" data-slug="' + esc(project.slug) + '">' +
      '<div class="project-row-left"><span class="card-dot"></span>' +
      '<div class="project-row-text">' +
      '<h3 class="project-row-title">' + esc(project.title) + "</h3>" +
      '<p class="project-row-desc">' + esc(project.description) + "</p>" +
      "</div></div>" +
      '<div class="project-row-right"><div class="project-row-tags">' +
      chips(project.tags, "row-tag") + "</div>" + EXT_ICON + "</div></a></div>"
    );
  }

  function questRow(quest) {
    return (
      '<div class="quest-row-wrap">' +
      '<a class="quest-row" data-link href="/projects/' + encodeURIComponent(quest.slug) +
      '" data-slug="' + esc(quest.slug) + '">' +
      '<div class="quest-row-left"><span class="status-dot ' + esc(quest.status) + '"></span>' +
      '<h3 class="quest-row-title">' + esc(quest.title) + "</h3>" +
      '<span class="quest-status-label ' + esc(quest.status) + '">' +
      (quest.status === "active" ? "● live" : "● in progress") + "</span></div>" +
      '<div class="quest-row-right"><div class="quest-row-specs">' +
      chips(quest.specs, "spec-tag") + "</div>" + EXT_ICON + "</div></a></div>"
    );
  }

  function galleryCard(image) {
    var owner = image.project;
    var src = image.thumbnail_url || image.url;
    return (
      '<div class="gallery-card">' +
      (src
        ? '<img class="gallery-img" src="' + esc(src) + '" alt="' + esc(image.label) +
          '" loading="lazy" decoding="async">'
        : '<div class="gallery-placeholder quest">' + IMAGE_ICON +
          '<span class="gallery-placeholder-label">' + esc(image.label) + "</span></div>") +
      '<div class="gallery-card-footer">' +
      (owner
        ? '<a class="gallery-source-tag quest" data-link href="/projects/' +
          encodeURIComponent(owner.slug) + '">' + esc(owner.title) + "</a>"
        : "") +
      "</div></div>"
    );
  }

  // ── views ─────────────────────────────────────────────────────────────────

  /* The bio, the photo frame and the status card are copy in the rendered
   * page's own template -- app/templates/components/_about_content.html -- and
   * not rows the API serves, so they are copy here too. Same wording and the
   * same order; if that file changes, this changes with it. */
  var BIO = [
    "I work in technical operations for a television and streaming production " +
    "company, managing infrastructure across AWS, on-prem networking, and " +
    "monitoring platforms. My days involve Splunk pipelines, Cisco switches, " +
    "and keeping production systems running smoothly.",
    "Outside of work, I run a Proxmox homelab that's become a full R&amp;D " +
    "environment — from self-hosted AI inference to network monitoring " +
    "experiments. I'm actively pursuing CCNA and CCNP Enterprise certifications."
  ];

  var STATUS = [
    ["Role:", "Technical Operations Engineer"],
    ["Cloud:", "AWS (EC2, S3, IAM, Lambda, RDS)"],
    ["Certs:", "CCNA / CCNP (in progress)"],
    ["Stack:", "Splunk · Grafana · Docker · Terraform"],
    ["Languages:", "Python, Java, Bash"],
    ["Networking:", "Cisco IOS · Palo Alto"],
    ["Platforms:", "Linux · Proxmox · Windows"],
    ["CI/CD:", "GitLab · OIDC · Terragrunt"]
  ];

  function home() {
    return get("/home").then(function (data) {
      var groups = {};
      (data.skills || []).forEach(function (skill) {
        (groups[skill.category] = groups[skill.category] || []).push(skill.name);
      });

      var skills = Object.keys(groups).map(function (category) {
        return (
          '<div class="skill-group"><h3 class="skill-group-title">// ' + esc(category) + "</h3>" +
          groups[category].map(function (name) {
            return '<div class="skill-item"><span class="skill-bullet">&#9654;</span> ' +
              esc(name) + "</div>";
          }).join("") + "</div>"
        );
      }).join("");

      var certs = (data.certifications || []).map(function (cert) {
        return (
          '<div class="cert-row"><div class="cert-row-left">' +
          '<span class="cert-status-dot ' + esc(cert.status) + '"></span>' +
          '<div class="cert-info"><span class="cert-name">' + esc(cert.name) + "</span>" +
          '<span class="cert-issuer">' + esc(cert.issuer) + "</span></div></div>" +
          '<span class="cert-year">' + esc(cert.year) + "</span></div>"
        );
      }).join("");

      var status = STATUS.map(function (row) {
        return '<div class="terminal-line"><span class="prefix">#</span>' +
          '<span class="accent">' + row[0] + "</span> " + esc(row[1]) + "</div>";
      }).join("");

      render(
        '<div class="home-page"><div>' +
        '<div class="fade-in"><div class="terminal-block">' +
        '<div class="terminal-line"><span class="prefix">$</span>whoami</div>' +
        '<div class="terminal-line"><span class="prefix">&rarr;</span> ' +
        '<span class="accent">Jeff Fredericks</span>' +
        " &mdash; Technical Operations &amp; Infrastructure Engineer</div></div></div>" +
        '<div class="fade-in"><h1 class="hero-title">Building systems ' +
        '<span class="accent italic">that scale</span><br>' +
        '&amp; automation that <span class="accent2 italic">endures</span></h1></div>' +
        '<div class="fade-in"><p class="hero-subtitle">Infrastructure engineer by ' +
        "trade. Python developer by practice. I design resilient systems, write " +
        "clean automation, and make sure everything keeps running at scale.</p></div>" +
        '<div class="fade-in"><div class="btn-row">' +
        '<a href="/projects" class="btn-primary" data-link>View Projects</a>' +
        '<a href="/contact" class="btn-secondary" data-link>Get in Touch</a>' +
        "</div></div></div></div>" +
        '<section id="about" class="home-about">' +
        heading("About", "fade-in") +
        '<div class="about-grid">' +
        '<div class="fade-in"><div class="photo-wrapper"><div class="photo-frame">' +
        '<span class="photo-initials">JF</span>' +
        '<span class="photo-label">your photo here</span></div>' +
        '<div class="photo-corner"></div></div></div>' +
        '<div class="fade-in"><p class="bio-text">' + BIO[0] + "</p>" +
        '<p class="bio-text bio-text--gap">' + BIO[1] + "</p></div></div>" +
        '<div class="fade-in"><div class="status-card">' +
        '<div class="status-card-header">/* current_status.py */</div>' +
        '<div class="status-grid">' + status + "</div></div></div>" +
        heading("Skills", "fade-in") +
        '<div class="skills-grid fade-in">' + skills + "</div>" +
        heading("Certifications", "fade-in") +
        '<div class="certs-list fade-in">' + certs + "</div>" +
        "</section>"
      );
    });
  }

  var TABS = [
    { key: "work", label: "Work" },
    { key: "sidequests", label: "Side Quests" },
    { key: "gallery", label: "Gallery" }
  ];

  /* Which projects list is in #view right now, or null for any other view --
   * render() clears it. Closing a detail panel navigates back to the list, and
   * without this that would refetch and rebuild markup that is already on
   * screen, throwing away the scroll position and replaying every fade-in. */
  var listKey = null;

  function projects(params) {
    var tab = params.get("tab") || "work";
    if (!TABS.some(function (t) { return t.key === tab; })) tab = "work";
    var page = parseInt(params.get("page"), 10) || 1;
    var key = tab + "#" + page;

    if (key === listKey) return Promise.resolve();
    loading();

    var href = function (n, key) {
      return "/projects?tab=" + (key || tab) + (n > 1 ? "&page=" + n : "");
    };

    var bar =
      '<div class="fade-in"><div class="sub-tab-bar"><div class="sub-tab-group">' +
      TABS.map(function (t) {
        return '<a class="sub-tab-btn' + (t.key === tab ? " active" : "") +
          '" data-link href="' + href(1, t.key) + '">' + t.label + "</a>";
      }).join("") + "</div></div></div>";

    var request = tab === "gallery"
      ? get("/gallery?page=" + page)
      : get("/projects?type=" + (tab === "work" ? "work" : "sidequest") + "&page=" + page);

    return request.then(function (data) {
      var noun = tab === "gallery" ? "image" : tab === "work" ? "project" : "side quest";
      var body;

      if (tab === "gallery") {
        body = '<div class="gallery-grid">' + data.items.map(galleryCard).join("") + "</div>";
      } else if (tab === "work") {
        body = '<div class="project-list">' + (data.items.length
          ? data.items.map(projectRow).join("")
          : '<p class="side-quests-intro">Nothing here yet.</p>') + "</div>";
      } else {
        body =
          '<div class="fade-in"><p class="side-quests-intro">The homelab is where ' +
          "I break things on purpose. It's a full R&amp;D environment for testing " +
          "infrastructure patterns, running AI workloads, and building skills that " +
          "transfer directly to production.</p></div>" +
          '<div class="quest-list">' + data.items.map(questRow).join("") + "</div>";
      }

      render(
        '<div class="projects-page">' + heading("Projects", "fade-in") + bar +
        '<div class="result-line result-line--solo">' + count(data.total, noun) + "</div>" +
        body +
        '<div class="panel-pager">' + pager(data, function (n) { return href(n); }) +
        "</div></div>"
      );
      listKey = key;
    });
  }

  /* ── The detail panel ──────────────────────────────────────────────────────
   *
   * A project opens as an overlay over the list it was clicked in, not as a
   * page of its own. That is what the rendered site does -- projects.js fetches
   * components/_detail_panel.html on click and slides it in from the right --
   * and the standalone projects/detail.html is only its no-JS fallback. This
   * shell has JS by definition, so it never renders the fallback.
   *
   * The URL still changes to /projects/<slug>: the address is shareable, Back
   * closes the panel, and a cold load of that address renders the list first
   * and opens the panel on top of it. */

  function panelSection(paths, label, inner) {
    return inner
      ? '<div class="panel-section"><div class="panel-section-label">' +
        icon(paths, 16) + "<span>" + label + "</span></div>" + inner + "</div>"
      : "";
  }

  function panelFiles(rows, trailing) {
    return (rows || []).length
      ? '<div class="panel-file-list">' + rows.map(function (file) {
          return '<div class="panel-file-item"><div>' +
            '<div class="panel-file-name">' + esc(file.name) + "</div>" +
            '<div class="panel-file-meta">' + esc(file.file_type || "") + "</div>" +
            "</div>" + trailing + "</div>";
        }).join("") + "</div>"
      : "";
  }

  function panelMarkup(item) {
    var isWork = item.type === "work";
    var dot = isWork ? item.category : item.status;
    var titleId = "panel-title-" + esc(item.slug);

    var gallery = (item.gallery || []).map(function (image) {
      var src = image.thumbnail_url || image.url;
      return src
        ? '<div class="panel-gallery-img-wrap"><img class="panel-gallery-img" src="' +
          esc(src) + '" alt="' + esc(image.label) + '" loading="lazy">' +
          '<span class="panel-gallery-img-label">' + esc(image.label) + "</span></div>"
        : '<div class="gallery-item">' + IMAGE_ICON + "<span>" + esc(image.label) +
          "</span></div>";
    }).join("");

    return (
      '<div class="detail-panel" id="panel-' + esc(item.slug) + '" role="dialog"' +
      ' aria-modal="true" aria-labelledby="' + titleId + '" tabindex="-1">' +
      '<div class="panel-header"><div class="panel-header-left">' +
      '<span class="panel-dot ' + esc(dot) + '"></span>' +
      '<h2 class="panel-title" id="' + titleId + '">' + esc(item.title) + "</h2></div>" +
      '<button class="panel-close-btn" type="button">&#10005; Close</button></div>' +
      '<div class="panel-body"><div class="panel-tags">' +
      chips(isWork ? item.tags : (item.specs || []), "panel-tag", 99) + "</div>" +
      '<p class="panel-long-desc">' + esc(item.long_description) + "</p>" +
      panelSection(GALLERY_PATHS, "Gallery",
        gallery ? '<div class="panel-gallery">' + gallery + "</div>" : "") +
      panelSection(DOCUMENT_PATHS, "Documents",
        panelFiles(item.documents, icon(EXT_PATHS, 14))) +
      panelSection(DOWNLOAD_PATHS, "Downloads",
        panelFiles(item.downloads, icon(DOWNLOAD_PATHS, 14, "dl-icon"))) +
      "</div></div>"
    );
  }

  var backdrop = document.getElementById("panel-backdrop");
  var panelHost = document.getElementById("panel-host");
  var activeRow = null;
  var lastFocus = null;
  var panelReturn = null;  // where dismissing the panel goes, when Back cannot

  var FOCUSABLE = 'a[href], button:not([disabled]), input, select, textarea, ' +
                  '[tabindex]:not([tabindex="-1"])';

  /* The panel is modal, so Tab must not walk out the back of it. */
  function trapFocus(event) {
    if (event.key !== "Tab") return;
    var panel = panelHost && panelHost.firstElementChild;
    if (!panel) return;
    var items = Array.prototype.filter.call(
      panel.querySelectorAll(FOCUSABLE),
      function (el) { return el.offsetParent !== null; }
    );
    if (!items.length) { event.preventDefault(); panel.focus(); return; }
    var first = items[0], last = items[items.length - 1], at = document.activeElement;
    // Focus starts on the panel itself, so Shift+Tab from there wraps to the end.
    if (event.shiftKey && (at === first || at === panel)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && at === last) {
      event.preventDefault();
      first.focus();
    }
  }

  /* While the panel is open the rest of the page stops existing: `inert` takes
   * it out of the tab order, off the accessibility tree, and out of reach of
   * clicks in one attribute. */
  function setBackgroundInert(on) {
    Array.prototype.forEach.call(document.body.children, function (el) {
      if (el === panelHost || el === backdrop) return;
      if (on) el.setAttribute("inert", "");
      else el.removeAttribute("inert");
    });
  }

  /* style.css locks <html> and <body>, which is the whole story on a page that
   * scrolls the window. Here <main> is the scroller, so it needs holding too or
   * the list keeps moving under the panel. */
  function lockScroll(on) {
    var scroller = document.querySelector("main");
    document.documentElement.classList.toggle("panel-open", on);
    if (scroller) scroller.style.overflowY = on ? "hidden" : "";
  }

  function rowFor(slug) {
    var rows = view.querySelectorAll(".project-row[data-slug], .quest-row[data-slug]");
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].getAttribute("data-slug") === slug) return rows[i];
    }
    return null;
  }

  function openPanel(item) {
    if (!panelHost) return;
    // Captured before `inert` lands: inerting the row's ancestor blurs it.
    lastFocus = document.activeElement;

    panelHost.innerHTML = panelMarkup(item);
    var panel = panelHost.firstElementChild;
    panel.classList.add("open");
    if (backdrop) backdrop.classList.add("open");
    lockScroll(true);
    setBackgroundInert(true);
    document.addEventListener("keydown", trapFocus, true);
    // The panel, not its first link: a reader lands on the title.
    panel.focus({ preventScroll: true });

    activeRow = rowFor(item.slug);
    if (activeRow) activeRow.classList.add("active");
  }

  /* Tears the panel down without touching history -- route() calls this, so it
   * must not navigate. */
  function closePanel() {
    if (!panelHost || !panelHost.firstElementChild) return;
    document.removeEventListener("keydown", trapFocus, true);
    panelHost.innerHTML = "";
    if (backdrop) backdrop.classList.remove("open");
    setBackgroundInert(false);
    lockScroll(false);
    if (activeRow) {
      activeRow.classList.remove("active");
      activeRow = null;
    }
    // Send the keyboard back to the row that opened this, not to the top.
    if (lastFocus && document.contains(lastFocus)) {
      lastFocus.focus({ preventScroll: true });
    }
    lastFocus = null;
  }

  /* Close, Escape and the backdrop all mean "go back to the list". Going back
   * through history keeps the list exactly as it was -- same page, same scroll
   * position; panelReturn is the fallback for a panel that was opened by URL,
   * where there is no history entry behind it to return to. */
  function dismissPanel() {
    if (!panelHost || !panelHost.firstElementChild) return;
    if (panelReturn) go(panelReturn);
    else window.history.back();
  }

  function projectDetail(slug) {
    return get("/projects/" + encodeURIComponent(slug)).then(function (item) {
      // A cold load has no list underneath yet; render the tab that owns this
      // item first, so closing the panel lands somewhere real.
      var tab = item.type === "work" ? "work" : "sidequests";
      var listShown = listKey !== null;
      panelReturn = listShown ? null : "/projects?tab=" + tab;
      var beneath = listShown
        ? Promise.resolve()
        : projects(new URLSearchParams("tab=" + tab));
      return beneath.then(function () { openPanel(item); });
    });
  }

  function posts(params) {
    var page = parseInt(params.get("page"), 10) || 1;
    return get("/posts?page=" + page).then(function (data) {
      render(
        '<div class="blog-page">' + heading("Blog", "fade-in") +
        '<div class="fade-in"><p class="blog-intro">Notes from the field — ' +
        "infrastructure war stories, homelab experiments, and things I learned " +
        "the hard way.</p></div>" +
        '<div class="blog-list">' + (data.items.length
          ? data.items.map(function (post) {
              return (
                '<div class="fade-in">' +
                '<a class="blog-card" data-link href="/blog/' +
                encodeURIComponent(post.slug) + '">' +
                '<div class="blog-card-top"><h3 class="blog-card-title">' +
                esc(post.title) + "</h3>" +
                '<div class="blog-card-tags">' + chips(post.tags, "blog-tag") + "</div></div>" +
                '<p class="blog-card-excerpt">' + esc(post.excerpt) + "</p>" +
                '<div class="blog-card-footer"><span class="blog-card-date">' +
                formatDate(post.date) + "</span></div></a></div>"
              );
            }).join("")
          : '<p class="blog-intro">No posts yet.</p>') + "</div>" +
        pager(data, function (n) { return "/blog?page=" + n; }) +
        "</div>"
      );
    });
  }

  function postDetail(slug) {
    return get("/posts/" + encodeURIComponent(slug)).then(function (post) {
      render(
        '<div class="blog-post-page">' +
        '<div class="fade-in">' +
        '<a href="/blog" class="back-link" data-link>&larr; Back to Blog</a></div>' +
        '<div class="fade-in">' +
        '<div class="blog-post-date">' + formatDate(post.date) + "</div>" +
        '<h1 class="blog-post-title">' + esc(post.title) + "</h1>" +
        '<div class="blog-post-tags">' + chips(post.tags, "blog-tag", 99) + "</div></div>" +
        '<div class="fade-in"><div class="blog-post-content">' +
        '<p class="blog-post-excerpt">' + esc(post.excerpt) + "</p>" +
        '<div class="blog-post-divider"></div>' +
        '<p class="blog-post-body">' + esc(post.content) + "</p></div></div></div>"
      );
    });
  }

  /* /search answers with results grouped by kind, not a flat list -- the same
   * five buckets the rendered page shows, each capped at `limit`. Flattening
   * them would throw away the grouping the endpoint went to the trouble of
   * producing, and a group that came back full gets a "see all" link. */
  function searchHit(href, title, snippet, trailing) {
    return '<a class="search-hit" data-link href="' + href + '">' +
      '<span class="search-hit-title">' + esc(title) + "</span>" +
      (snippet ? '<span class="search-hit-snippet">' + esc(snippet) + "</span>" : "") +
      (trailing || "") + "</a>";
  }

  function searchGroup(label, more, inner) {
    return '<section class="search-group fade-in"><h3 class="search-group-title">' + label +
      (more ? '<a class="search-group-more" data-link href="' + more +
        '">see all &rarr;</a>' : "") + "</h3>" + inner + "</section>";
  }

  function search(params) {
    var q = params.get("q") || "";
    document.querySelector(".nav-search-input").value = q;

    return get("/search?q=" + encodeURIComponent(q)).then(function (data) {
      var groups = data.results;
      var full = function (rows) { return rows.length === data.limit; };
      var body;

      if (!q) {
        body = '<p class="search-empty fade-in">Searches titles, descriptions, specs, ' +
          "gallery labels and post bodies. Quote a phrase to match it exactly; " +
          "prefix a word with <code>-</code> to exclude it.</p>";
      } else if (data.too_short) {
        body = '<p class="search-empty fade-in">Two characters or more, please &mdash; ' +
          "one letter matches almost everything.</p>";
      } else if (!data.total) {
        body = '<p class="search-empty fade-in">Nothing matches <strong>' + esc(q) +
          "</strong>. Matching is by word stem, so partial words like " +
          "<code>prox</code> only find tags &mdash; try the whole word.</p>";
      } else {
        body = '<p class="search-count fade-in">' + data.total + " result" +
          (data.total === 1 ? "" : "s") + " for <strong>" + esc(q) + "</strong></p>";

        if (groups.tags.length) {
          body += searchGroup("Tags", "", '<div class="search-tag-row">' +
            groups.tags.map(function (tag) {
              return '<span class="blog-tag">' + esc(tag.name) + "</span>";
            }).join("") + "</div>");
        }

        [["work", "Work", "work"], ["sidequests", "Side Quests", "sidequests"]]
          .forEach(function (spec) {
            var rows = groups[spec[0]];
            if (!rows.length) return;
            body += searchGroup(spec[1], full(rows) ? "/projects?tab=" + spec[2] : "",
              '<div class="search-hit-list">' + rows.map(function (item) {
                return searchHit(
                  "/projects/" + encodeURIComponent(item.slug),
                  item.title, item.description,
                  item.tags && item.tags.length
                    ? '<span class="search-hit-tags">' + chips(item.tags, "blog-tag") +
                      "</span>"
                    : ""
                );
              }).join("") + "</div>");
          });

        if (groups.posts.length) {
          body += searchGroup("Blog", full(groups.posts) ? "/blog" : "",
            '<div class="search-hit-list">' + groups.posts.map(function (post) {
              return searchHit(
                "/blog/" + encodeURIComponent(post.slug), post.title, post.excerpt,
                post.date
                  ? '<span class="search-hit-meta">' + formatDate(post.date) + "</span>"
                  : ""
              );
            }).join("") + "</div>");
        }

        if (groups.gallery.length) {
          body += searchGroup("Gallery", full(groups.gallery) ? "/projects?tab=gallery" : "",
            '<div class="gallery-grid">' + groups.gallery.map(galleryCard).join("") + "</div>");
        }
      }

      render(
        '<div class="search-page">' + heading("Search", "fade-in") +
        '<form class="search-hero fade-in" role="search" data-search>' +
        '<label class="visually-hidden" for="search-hero-input">Search</label>' +
        '<input id="search-hero-input" class="search-hero-input" type="search" name="q"' +
        ' value="' + esc(q) + '" placeholder="projects, side quests, gallery, posts"' +
        ' autocomplete="off" spellcheck="false"' + (q ? "" : " autofocus") + ">" +
        '<button class="search-hero-btn" type="submit">Search</button></form>' +
        body + "</div>"
      );
    });
  }

  /* The only view with no API behind it: the contact details are copy, not
   * content, and putting them in the database to satisfy a pattern would make
   * them harder to edit rather than easier. The rendered page hangs an email
   * app picker off the first row; here it is a plain mailto, because the
   * picker is contact.js and this shell does not load the site's scripts. */
  var CONTACT_ICON = {
    email: '<rect width="20" height="16" x="2" y="4" rx="2"/>' +
      '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    phone: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5' +
      ' 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.61 2h3a2 2 0 0 1' +
      ' 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6' +
      ' 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    github: '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1' +
      '-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3' +
      ' 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05' +
      '-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
    linkedin: '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4' +
      'v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/>' +
      '<circle cx="4" cy="4" r="2"/>',
    discord: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    schedule: '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/>' +
      '<line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/>' +
      '<line x1="3" x2="21" y1="10" y2="10"/>'
  };

  var CONTACT_LINKS = [
    { icon: "email", label: "Email", value: "your.email@example.com",
      href: "mailto:your.email@example.com" },
    { icon: "phone", label: "Phone", value: "(555) 123-4567", href: "tel:+15551234567" },
    { icon: "github", label: "GitHub", value: "github.com/yourusername",
      href: "https://github.com/yourusername", external: true },
    { icon: "linkedin", label: "LinkedIn", value: "linkedin.com/in/yourprofile",
      href: "https://linkedin.com/in/yourprofile", external: true },
    { icon: "discord", label: "Discord", value: "yourhandle" },
    { icon: "schedule", label: "Schedule", value: "Coming soon", muted: true }
  ];

  function contactLink(row) {
    var svg = '<svg class="contact-icon" xmlns="http://www.w3.org/2000/svg"' +
      ' viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      CONTACT_ICON[row.icon] + "</svg>";
    var inner = svg +
      '<span class="contact-label">' + esc(row.label) + "</span>" +
      '<span class="contact-value' + (row.muted ? " contact-value--muted" : "") + '">' +
      esc(row.value) + "</span>";
    return row.href
      ? '<a class="contact-link" href="' + esc(row.href) + '"' +
        (row.external ? ' target="_blank" rel="noopener noreferrer"' : "") + ">" +
        inner + "</a>"
      : '<div class="contact-link contact-link--disabled">' + inner + "</div>";
  }

  function contact() {
    render(
      '<div class="contact-page">' + heading("Get In Touch", "fade-in") +
      '<div class="fade-in"><div class="contact-card"><p class="contact-intro">' +
      "Whether it's infrastructure consulting, a Python project, or just " +
      "talking shop about homelabs &mdash; I'd like to hear from you.</p>" +
      '<div class="contact-links">' + CONTACT_LINKS.map(contactLink).join("") +
      "</div></div></div>" +
      '<div class="fade-in"><div class="resume-row">' +
      '<button class="btn-primary resume-btn">' +
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"' +
      ' viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
      '<polyline points="7 10 12 15 17 10"/>' +
      '<line x1="12" x2="12" y1="15" y2="3"/></svg>Download Resume</button>' +
      '<span class="resume-meta">PDF &middot; Updated 2026</span></div></div></div>'
    );
    return Promise.resolve();
  }

  // ── routing ───────────────────────────────────────────────────────────────

  /* The fourth field is "owns its own loading state". The two projects routes
   * do: one reuses a list it may already have rendered, the other opens a panel
   * over it, and blanking #view first would undo both. */
  var ROUTES = [
    [/^\/$/, home, "home"],
    [/^\/projects$/, projects, "projects", true],
    [/^\/projects\/([^/]+)$/, function (params, slug) { return projectDetail(slug); },
      "projects", true],
    [/^\/blog$/, posts, "blog"],
    [/^\/blog\/([^/]+)$/, function (params, slug) { return postDetail(slug); }, "blog"],
    [/^\/search$/, search, "search"],
    [/^\/contact$/, contact, "contact"]
  ];

  function route() {
    var path = window.location.pathname.replace(/\/+$/, "") || "/";
    var params = new URLSearchParams(window.location.search);

    // Any navigation at all leaves the panel behind, Back included.
    closePanel();

    for (var i = 0; i < ROUTES.length; i++) {
      var match = path.match(ROUTES[i][0]);
      if (!match) continue;

      var section = ROUTES[i][2];
      document.querySelectorAll(".nav-btn").forEach(function (link) {
        link.classList.toggle("active", link.dataset.section === section);
      });
      if (section !== "search") document.querySelector(".nav-search-input").value = "";

      if (!ROUTES[i][3]) loading();
      var args = [params].concat(match.slice(1).map(decodeURIComponent));
      ROUTES[i][1].apply(null, args).catch(failed);
      return;
    }
    failed({ status: 404 });
  }

  function go(url) {
    window.history.pushState({}, "", url);
    route();
  }

  /* One listener on the document rather than one per link: the views replace
   * their own markup on every render, and per-link listeners would have to be
   * reattached each time. */
  document.addEventListener("click", function (event) {
    if (event.target.closest(".panel-close-btn")) {
      dismissPanel();
      return;
    }
    if (backdrop && event.target === backdrop) {
      dismissPanel();
      return;
    }

    var link = event.target.closest("a[data-link]");
    if (!link) return;
    // Let the browser handle anything the user asked to open elsewhere.
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    go(link.getAttribute("href"));
  });

  document.addEventListener("submit", function (event) {
    var form = event.target.closest("form[data-search]");
    if (!form) return;
    event.preventDefault();
    go("/search?q=" + encodeURIComponent(form.elements.q.value));
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") dismissPanel();
  });

  window.addEventListener("popstate", route);

  var toggle = document.querySelector(".nav-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      document.getElementById("nav-links").classList.toggle("open", !open);
    });
  }

  route();
})();
