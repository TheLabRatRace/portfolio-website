/* Projects page behaviour. Every handler is delegated from `document`: rows
 * arrive by pagination and panels by fetch, so per-element binding would mean
 * rebinding after every change. */
document.addEventListener('DOMContentLoaded', () => {
    const backdrop   = document.getElementById('panel-backdrop');
    const panelHost  = document.getElementById('panel-host');
    const lightbox   = document.getElementById('gallery-lightbox');

    // ── Every overlay lives on <body> ──
    // <main> keeps a transform from `animation: pageIn ... both`, and a
    // transformed ancestor is the containing block for its position:fixed
    // descendants -- overlays left inside it pin to <main>, not the viewport.
    [backdrop, panelHost, lightbox].forEach(el => el && document.body.appendChild(el));

    // ── Scroll lock ──
    // Two overlays can want the page held still, so the release asks who is
    // still open rather than each one clobbering the other's overflow. The
    // padding keeps the layout from jumping as the scrollbar disappears.
    function lockScroll() {
        const gap = window.innerWidth - document.documentElement.clientWidth;
        if (gap > 0) document.body.style.paddingRight = `${gap}px`;
        document.documentElement.classList.add('panel-open');
    }

    function releaseScrollIfIdle() {
        if (panelHost && panelHost.firstElementChild) return;
        if (lightbox && !lightbox.hidden) return;
        document.documentElement.classList.remove('panel-open');
        document.body.style.paddingRight = '';
    }

    // ── Detail panels (fetched on demand) ──
    const panelCache = new Map();
    let activeRow = null;
    let pending = null;
    let lastFocus = null;

    const FOCUSABLE = 'a[href], button:not([disabled]), input, select, textarea, ' +
                      '[tabindex]:not([tabindex="-1"])';

    // The panel is modal, so Tab must not walk out the back of it.
    function trapFocus(e) {
        if (e.key !== 'Tab') return;
        const panel = panelHost && panelHost.querySelector('.detail-panel');
        if (!panel) return;
        const items = Array.from(panel.querySelectorAll(FOCUSABLE))
                           .filter(el => el.offsetParent !== null);
        if (!items.length) { e.preventDefault(); panel.focus(); return; }
        const first = items[0];
        const last  = items[items.length - 1];
        const at    = document.activeElement;
        // Focus starts on the panel itself, so Shift+Tab from there wraps to the end.
        if (e.shiftKey && (at === first || at === panel)) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && at === last) {
            e.preventDefault();
            first.focus();
        }
    }

    // While the panel is open the rest of the page stops existing: `inert` takes
    // it out of the tab order, off the accessibility tree, and out of reach of
    // clicks in one attribute. The lightbox is exempt -- panel images open it.
    function setBackgroundInert(on) {
        Array.from(document.body.children).forEach(el => {
            if (el === panelHost || el === backdrop || el === lightbox) return;
            if (on) el.setAttribute('inert', '');
            else el.removeAttribute('inert');
        });
    }

    async function fetchPanel(slug) {
        if (panelCache.has(slug)) return panelCache.get(slug);
        const res = await fetch(`/projects/panel/${encodeURIComponent(slug)}`, {
            headers: { 'Accept': 'text/html' }
        });
        if (!res.ok) throw new Error(`panel ${slug}: ${res.status}`);
        const html = await res.text();
        panelCache.set(slug, html);
        return html;
    }

    async function openPanel(slug, row) {
        if (!panelHost) return;
        // Swapping panels should not bounce focus back to the old row on the way.
        closePanel({ restoreFocus: false });
        pending = slug;
        let html;
        try {
            html = await fetchPanel(slug);
        } catch (err) {
            console.error(err);
            // The row is a real link -- fall back to the full page.
            window.location.href = `/projects/${encodeURIComponent(slug)}`;
            return;
        }
        // A second row may have been clicked while this fetch was in flight.
        if (pending !== slug) return;

        lastFocus = row || document.activeElement;

        panelHost.innerHTML = html;
        const panel = panelHost.querySelector('.detail-panel');
        if (!panel) return;
        panel.classList.add('open');
        if (backdrop) backdrop.classList.add('open');
        lockScroll();
        setBackgroundInert(true);
        document.addEventListener('keydown', trapFocus, true);
        // The panel, not its first link: a reader lands on the title.
        panel.focus({ preventScroll: true });
        if (row) {
            row.classList.add('active');
            activeRow = row;
        }
    }

    function closePanel({ restoreFocus = true } = {}) {
        const wasOpen = panelHost && panelHost.firstElementChild;
        pending = null;
        document.removeEventListener('keydown', trapFocus, true);
        if (panelHost) panelHost.innerHTML = '';
        if (backdrop) backdrop.classList.remove('open');
        setBackgroundInert(false);
        releaseScrollIfIdle();
        if (activeRow) {
            activeRow.classList.remove('active');
            activeRow = null;
        }
        // Send the keyboard back to the row that opened this, not to the top.
        if (wasOpen && restoreFocus && lastFocus && document.contains(lastFocus)) {
            lastFocus.focus({ preventScroll: true });
        }
        if (restoreFocus) lastFocus = null;
    }

    // ── Lightbox ──
    let lbImg, lbLabel, lbSource, lbFrame, lbPrev, lbNext;
    if (lightbox) {
        lbImg    = lightbox.querySelector('.lightbox-img');
        lbLabel  = lightbox.querySelector('.lightbox-caption-label');
        lbSource = lightbox.querySelector('.lightbox-caption-source');
        lbFrame  = lightbox.querySelector('.lightbox-frame');
        lbPrev   = lightbox.querySelector('.lightbox-prev');
        lbNext   = lightbox.querySelector('.lightbox-next');
    }

    let lbIndex = 0;

    // Recomputed per open: the gallery changes with pagination.
    const galleryImgs = () => Array.from(document.querySelectorAll('.gallery-img'));

    function openLightbox(index) {
        const imgs = galleryImgs();
        const imgEl = imgs[index];
        if (!imgEl) return;
        const card   = imgEl.closest('.gallery-card');
        const footer = card ? card.querySelector('.gallery-source-tag') : null;
        lbIndex = index;
        lbImg.src            = imgEl.src;
        lbImg.alt            = imgEl.alt;
        lbLabel.textContent  = imgEl.alt;
        lbSource.textContent = footer ? footer.textContent.trim() : '';
        lbPrev.disabled      = index === 0;
        lbNext.disabled      = index === imgs.length - 1;
        lightbox.hidden      = false;
        lockScroll();
    }

    function openLightboxSingle(src, alt, source) {
        lbIndex = -1;
        lbImg.src            = src;
        lbImg.alt            = alt;
        lbLabel.textContent  = alt;
        lbSource.textContent = source;
        lbPrev.disabled      = true;
        lbNext.disabled      = true;
        lightbox.hidden      = false;
        lockScroll();
    }

    function closeLightbox() {
        if (!lightbox) return;
        lightbox.hidden = true;
        lbImg.src = '';
        // Closing the lightbox must not unlock the page out from under a panel
        // that is still open behind it.
        releaseScrollIfIdle();
    }

    // ── Tabs ──
    function showTab(name) {
        document.querySelectorAll('.sub-tab-btn').forEach(b =>
            b.classList.toggle('active', b.dataset.tab === name));
        document.querySelectorAll('.tab-panel').forEach(p =>
            p.classList.toggle('hidden', p.id !== `tab-${name}`));
        // Each tab owns a pager in the bar; swap it with the panel.
        document.querySelectorAll('.tab-pager').forEach(p =>
            p.classList.toggle('hidden', p.dataset.tab !== name));
    }

    // ── One delegated click handler for the whole page ──
    document.addEventListener('click', e => {
        // Let the browser handle modified clicks (new tab, new window).
        const plain = !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) && e.button === 0;

        const row = e.target.closest('.project-row[data-slug], .quest-row[data-slug]');
        if (row && plain) {
            e.preventDefault();
            openPanel(row.dataset.slug, row);
            return;
        }

        const tabBtn = e.target.closest('.sub-tab-btn');
        if (tabBtn && plain) {
            e.preventDefault();
            showTab(tabBtn.dataset.tab);
            history.replaceState(null, '', tabBtn.href);
            return;
        }

        if (e.target.closest('button.panel-close-btn')) {
            closePanel();
            return;
        }

        if (backdrop && e.target === backdrop) {
            closePanel();
            return;
        }

        const galleryImg = e.target.closest('.gallery-img');
        if (galleryImg) {
            openLightbox(galleryImgs().indexOf(galleryImg));
            return;
        }

        const panelImg = e.target.closest('.panel-gallery-img');
        if (panelImg) {
            const panel = panelImg.closest('.detail-panel');
            const title = panel ? panel.querySelector('.panel-title') : null;
            openLightboxSingle(panelImg.src, panelImg.alt,
                               title ? title.textContent.trim() : '');
            return;
        }

        if (!lightbox || lightbox.hidden) return;

        if (e.target.closest('.lightbox-prev')) {
            e.stopPropagation();
            if (lbIndex > 0) openLightbox(lbIndex - 1);
            return;
        }
        if (e.target.closest('.lightbox-next')) {
            e.stopPropagation();
            if (lbIndex >= 0 && lbIndex < galleryImgs().length - 1) openLightbox(lbIndex + 1);
            return;
        }
        if (e.target.closest('.lightbox-close')) {
            closeLightbox();
            return;
        }
        // Anywhere outside the image frame closes it.
        if (lightbox.contains(e.target) && !lbFrame.contains(e.target)) {
            closeLightbox();
        }
    });

    document.addEventListener('keydown', e => {
        if (lightbox && !lightbox.hidden) {
            const imgs = galleryImgs();
            if (e.key === 'Escape')     { e.preventDefault(); closeLightbox(); }
            if (e.key === 'ArrowLeft')  { e.preventDefault(); if (lbIndex > 0) openLightbox(lbIndex - 1); }
            if (e.key === 'ArrowRight') { e.preventDefault(); if (lbIndex >= 0 && lbIndex < imgs.length - 1) openLightbox(lbIndex + 1); }
        } else if (e.key === 'Escape') {
            closePanel();
        }
    });
});
