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
    view.innerHTML = html;
    view.setAttribute("aria-busy", "false");
    window.scrollTo(0, 0);
  }

  function loading() {
    view.setAttribute("aria-busy", "true");
    view.innerHTML = '<div class="projects-page"><p class="blog-intro">Loading…</p></div>';
  }

  function failed(error) {
    var missing = error && error.status === 404;
    render(
      '<div class="error-page">' +
      heading(missing ? "Not found" : "Something went wrong") +
      '<p class="blog-intro">' +
      (missing
        ? "That page isn't here."
        : "The content service didn't answer. Try again in a moment.") +
      "</p>" +
      '<a href="/" class="btn-primary" data-link>Go home</a></div>'
    );
  }

  function heading(text) {
    return '<div class="section-heading"><h2>' + esc(text) +
      '</h2><div class="section-heading-bar"></div></div>';
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

  var EXT_ICON =
    '<svg class="ext-link-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16"' +
    ' viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/>' +
    '<path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>';

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
      encodeURIComponent(project.slug) + '">' +
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
      '<a class="quest-row" data-link href="/projects/' + encodeURIComponent(quest.slug) + '">' +
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

      render(
        '<div class="home-page"><div>' +
        '<div class="terminal-block">' +
        '<div class="terminal-line"><span class="prefix">$</span>whoami</div>' +
        '<div class="terminal-line"><span class="prefix">&rarr;</span> ' +
        '<span class="accent">Jeff Fredericks</span>' +
        " &mdash; Technical Operations &amp; Infrastructure Engineer</div></div>" +
        '<h1 class="hero-title">Building systems ' +
        '<span class="accent italic">that scale</span><br>' +
        '&amp; automation that <span class="accent2 italic">endures</span></h1>' +
        '<p class="hero-subtitle">Infrastructure engineer by trade. Python developer ' +
        "by practice. I design resilient systems, write clean automation, and make " +
        "sure everything keeps running at scale.</p>" +
        '<div class="btn-row">' +
        '<a href="/projects" class="btn-primary" data-link>View Projects</a>' +
        '<a href="/contact" class="btn-secondary" data-link>Get in Touch</a>' +
        "</div></div></div>" +
        '<section id="about" class="home-about">' +
        heading("Skills") + '<div class="skills-grid">' + skills + "</div>" +
        heading("Certifications") + '<div class="certs-list">' + certs + "</div>" +
        "</section>"
      );
    });
  }

  var TABS = [
    { key: "work", label: "Work" },
    { key: "sidequests", label: "Side Quests" },
    { key: "gallery", label: "Gallery" }
  ];

  function projects(params) {
    var tab = params.get("tab") || "work";
    if (!TABS.some(function (t) { return t.key === tab; })) tab = "work";
    var page = parseInt(params.get("page"), 10) || 1;

    var href = function (n, key) {
      return "/projects?tab=" + (key || tab) + (n > 1 ? "&page=" + n : "");
    };

    var bar =
      '<div class="sub-tab-bar"><div class="sub-tab-group">' +
      TABS.map(function (t) {
        return '<a class="sub-tab-btn' + (t.key === tab ? " active" : "") +
          '" data-link href="' + href(1, t.key) + '">' + t.label + "</a>";
      }).join("") + "</div></div>";

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
          '<p class="side-quests-intro">The homelab is where I break things on ' +
          "purpose. It's a full R&amp;D environment for testing infrastructure " +
          "patterns, running AI workloads, and building skills that transfer " +
          "directly to production.</p>" +
          '<div class="quest-list">' + data.items.map(questRow).join("") + "</div>";
      }

      render(
        '<div class="projects-page">' + heading("Projects") + bar +
        '<div class="result-line result-line--solo">' + count(data.total, noun) + "</div>" +
        body +
        '<div class="panel-pager">' + pager(data, function (n) { return href(n); }) +
        "</div></div>"
      );
    });
  }

  function projectDetail(slug) {
    return get("/projects/" + encodeURIComponent(slug)).then(function (item) {
      var isWork = item.type === "work";
      var panelChips = isWork ? item.tags : (item.specs || []);
      var dot = isWork ? item.category : item.status;

      function section(label, inner) {
        return inner
          ? '<div class="panel-section"><div class="panel-section-label"><span>' +
            label + "</span></div>" + inner + "</div>"
          : "";
      }

      var gallery = (item.gallery || []).map(function (image) {
        var src = image.thumbnail_url || image.url;
        return src
          ? '<div class="panel-gallery-img-wrap"><img class="panel-gallery-img" src="' +
            esc(src) + '" alt="' + esc(image.label) + '" loading="lazy">' +
            '<span class="panel-gallery-img-label">' + esc(image.label) + "</span></div>"
          : '<div class="gallery-item">' + IMAGE_ICON + "<span>" + esc(image.label) +
            "</span></div>";
      }).join("");

      function fileList(rows) {
        return (rows || []).length
          ? '<div class="panel-file-list">' + rows.map(function (file) {
              return '<div class="panel-file-item"><div>' +
                '<div class="panel-file-name">' + esc(file.name) + "</div>" +
                '<div class="panel-file-meta">' + esc(file.file_type || "") + "</div>" +
                "</div>" + EXT_ICON + "</div>";
            }).join("") + "</div>"
          : "";
      }

      render(
        '<div class="projects-page">' + heading(item.title) +
        '<div class="detail-panel detail-panel--page">' +
        '<div class="panel-header"><div class="panel-header-left">' +
        '<span class="panel-dot ' + esc(dot) + '"></span>' +
        '<h2 class="panel-title">' + esc(item.title) + "</h2></div>" +
        '<a class="panel-close-btn" href="/projects" data-link>&larr; All projects</a></div>' +
        '<div class="panel-body"><div class="panel-tags">' +
        chips(panelChips, "panel-tag", 99) + "</div>" +
        '<p class="panel-long-desc">' + esc(item.long_description) + "</p>" +
        section("Gallery", gallery ? '<div class="panel-gallery">' + gallery + "</div>" : "") +
        section("Documents", fileList(item.documents)) +
        section("Downloads", fileList(item.downloads)) +
        "</div></div></div>"
      );
    });
  }

  function posts(params) {
    var page = parseInt(params.get("page"), 10) || 1;
    return get("/posts?page=" + page).then(function (data) {
      render(
        '<div class="blog-page">' + heading("Blog") +
        '<p class="blog-intro">Notes from the field — infrastructure war stories, ' +
        "homelab experiments, and things I learned the hard way.</p>" +
        '<div class="blog-list">' + (data.items.length
          ? data.items.map(function (post) {
              return (
                '<a class="blog-card" data-link href="/blog/' +
                encodeURIComponent(post.slug) + '">' +
                '<div class="blog-card-top"><h3 class="blog-card-title">' +
                esc(post.title) + "</h3>" +
                '<div class="blog-card-tags">' + chips(post.tags, "blog-tag") + "</div></div>" +
                '<p class="blog-card-excerpt">' + esc(post.excerpt) + "</p>" +
                '<div class="blog-card-footer"><span class="blog-card-date">' +
                formatDate(post.date) + "</span></div></a>"
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
        '<a href="/blog" class="back-link" data-link>&larr; Back to Blog</a>' +
        '<div class="blog-post-date">' + formatDate(post.date) + "</div>" +
        '<h1 class="blog-post-title">' + esc(post.title) + "</h1>" +
        '<div class="blog-post-tags">' + chips(post.tags, "blog-tag", 99) + "</div>" +
        '<div class="blog-post-content">' +
        '<p class="blog-post-excerpt">' + esc(post.excerpt) + "</p>" +
        '<div class="blog-post-divider"></div>' +
        '<p class="blog-post-body">' + esc(post.content) + "</p></div></div>"
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
    return '<section class="search-group"><h3 class="search-group-title">' + label +
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
        body = '<p class="search-empty">Searches titles, descriptions, specs, ' +
          "gallery labels and post bodies. Quote a phrase to match it exactly; " +
          "prefix a word with <code>-</code> to exclude it.</p>";
      } else if (data.too_short) {
        body = '<p class="search-empty">Two characters or more, please &mdash; ' +
          "one letter matches almost everything.</p>";
      } else if (!data.total) {
        body = '<p class="search-empty">Nothing matches <strong>' + esc(q) +
          "</strong>. Matching is by word stem, so partial words like " +
          "<code>prox</code> only find tags &mdash; try the whole word.</p>";
      } else {
        body = '<p class="search-count">' + data.total + " result" +
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
        '<div class="search-page">' + heading("Search") +
        '<form class="search-hero" role="search" data-search>' +
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
      '<div class="contact-page">' + heading("Get In Touch") +
      '<div class="contact-card"><p class="contact-intro">' +
      "Whether it's infrastructure consulting, a Python project, or just " +
      "talking shop about homelabs &mdash; I'd like to hear from you.</p>" +
      '<div class="contact-links">' + CONTACT_LINKS.map(contactLink).join("") +
      "</div></div>" +
      '<div class="resume-row"><button class="btn-primary resume-btn">' +
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"' +
      ' viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
      '<polyline points="7 10 12 15 17 10"/>' +
      '<line x1="12" x2="12" y1="15" y2="3"/></svg>Download Resume</button>' +
      '<span class="resume-meta">PDF &middot; Updated 2026</span></div></div>'
    );
    return Promise.resolve();
  }

  // ── routing ───────────────────────────────────────────────────────────────

  var ROUTES = [
    [/^\/$/, home, "home"],
    [/^\/projects$/, projects, "projects"],
    [/^\/projects\/([^/]+)$/, function (params, slug) { return projectDetail(slug); }, "projects"],
    [/^\/blog$/, posts, "blog"],
    [/^\/blog\/([^/]+)$/, function (params, slug) { return postDetail(slug); }, "blog"],
    [/^\/search$/, search, "search"],
    [/^\/contact$/, contact, "contact"]
  ];

  function route() {
    var path = window.location.pathname.replace(/\/+$/, "") || "/";
    var params = new URLSearchParams(window.location.search);

    for (var i = 0; i < ROUTES.length; i++) {
      var match = path.match(ROUTES[i][0]);
      if (!match) continue;

      var section = ROUTES[i][2];
      document.querySelectorAll(".nav-btn").forEach(function (link) {
        link.classList.toggle("active", link.dataset.section === section);
      });
      if (section !== "search") document.querySelector(".nav-search-input").value = "";

      loading();
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
