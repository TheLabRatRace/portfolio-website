---
name: Bug
about: Something already in the repo behaves wrongly.
title: ''
labels: bug
---

<!-- Do NOT use this template for a security vulnerability — see SECURITY.md
     and use private vulnerability reporting instead. -->

### What happens

<!-- One sentence. The observable behaviour, not the theory. -->

### What should happen

### Steps to reproduce

1.
2.
3.

### Where

- [ ] `/` — the home page, including the About section folded into it
- [ ] `/contact`
- [ ] `/projects/` — which tab? work / sidequests / gallery
- [ ] `/projects/<slug>` full page, or the fetched detail panel
- [ ] `/blog/`
- [ ] `/search`
- [ ] `/admin/` — which page?
- [ ] tooling in `tools/`
- [ ] the container / compose stack itself

### Environment

| | |
|---|---|
| viewport width | <!-- layout bugs are almost always breakpoint bugs: 640 / 900 / 1024 / 1199 --> |
| device pixel ratio | <!-- srcset picks a different file at DPR 2 --> |
| browser | |
| per-page setting | <!-- 10 / 25 / 50 --> |
| data | seeded 11 projects / stress-seeded / other |

### Evidence

<!-- Screenshot, the failing assertion, the response body, or the console
     error. For a layout bug a screenshot at the exact width beats a
     description of it. -->
