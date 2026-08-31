/* Viewport audit -- paste into any browser console, or run via a devtools
 * protocol client. Reports layout defects at the CURRENT viewport size.
 *
 * There is no headless-browser dependency here on purpose: this site has no
 * package.json, and pulling in Playwright to check for horizontal overflow
 * would be a heavier commitment than the check is worth. Resize the window
 * (or use device emulation) and re-run.
 *
 * NOTE ON MEASURING WITH DEVICE EMULATION: Chrome re-evaluates media queries
 * on resize, but a page that was laid out at another width can keep stale
 * computed styles. Reload after every resize before reading anything, or you
 * will measure the previous viewport's rules and chase a bug that isn't there.
 *
 *   auditViewport()            -> report for the current size
 *   auditViewport({verbose:1}) -> also lists every offending element
 *
 * The matrix worth checking, and why each one is in it:
 *    320 x 800   Galaxy Fold cover screen -- the narrowest real viewport
 *    375 x 667   iPhone SE, and the shortest common phone
 *    390 x 844   modern iPhone
 *    707 x 823   Galaxy Z Fold 6 unfolded -- near-square, narrower than an iPad
 *    768 x 1024  iPad portrait
 *    884 x 1104  Galaxy Z Fold 2 unfolded
 *   1024 x 768   iPad landscape
 *   1280 x 700   laptop, deliberately short to catch vh/dvh bugs
 *   1920 x 1080  desktop
 *   2560 x 1440  large desktop
 */
function inScrollerX(el) {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        const ox = getComputedStyle(p).overflowX;
        if (ox === 'auto' || ox === 'scroll') return true;
    }
    return false;
}

function auditViewport({ verbose = false } = {}) {
    const vw = document.documentElement.clientWidth;
    const overflowing = [];
    const clipped = [];

    for (const el of document.querySelectorAll('body *')) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') continue;
        // Fixed overlays are positioned against the viewport deliberately.
        if (cs.position === 'fixed') continue;
        // Content inside a horizontal scroller is reachable by scrolling, so it
        // is not clipped -- only the scroller's own box has to fit.
        if (el.closest('[data-scroll-x]') || inScrollerX(el)) continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        const tag = el.tagName.toLowerCase() +
                    (el.className && typeof el.className === 'string'
                        ? '.' + el.className.trim().split(/\s+/).join('.')
                        : '');
        // Past the right edge with no way to scroll to it = silently cut off.
        if (r.right > vw + 1) (document.documentElement.scrollWidth > vw ? overflowing : clipped)
            .push({ el: tag, right: Math.round(r.right), over: Math.round(r.right - vw) });
        if (r.left < -1) overflowing.push({ el: tag, left: Math.round(r.left) });
    }

    // An element wider than the viewport is the usual root cause; report the
    // outermost one rather than every descendant it drags past the edge.
    const roots = list => list.filter(a =>
        !list.some(b => b !== a && a.el.startsWith(b.el.split('.')[0]) && b.over > a.over));

    const report = {
        viewport: `${vw} x ${document.documentElement.clientHeight}`,
        dpr: window.devicePixelRatio,
        horizontalScroll: document.documentElement.scrollWidth > vw,
        scrollWidth: document.documentElement.scrollWidth,
        clippedCount: clipped.length,
        overflowCount: overflowing.length,
        pass: document.documentElement.scrollWidth <= vw && clipped.length === 0,
    };
    if (verbose || !report.pass) {
        report.clipped = roots(clipped).slice(0, 10);
        report.overflowing = roots(overflowing).slice(0, 10);
    }
    return report;
}

if (typeof module !== 'undefined') module.exports = { auditViewport };
