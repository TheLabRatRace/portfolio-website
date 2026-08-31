/* Site-wide behaviour. Page-specific logic (tabs, filters, panels) lives in
 * that page's own script, so no two files handle the same event. */
document.addEventListener('DOMContentLoaded', () => {
    setUpNav();

    const animated = document.querySelectorAll('.fade-in, .terminal-line');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reduceMotion || !('IntersectionObserver' in window)) {
        animated.forEach(el => el.classList.add('visible'));
        return;
    }

    /* Reveal on scroll, not on a timer ladder: cost no longer scales with how
     * much is on the page. The stagger is an element's position in the batch
     * that just came into view -- the only thing a stagger needs to know, and
     * the only thing that stays correct however the reader arrives. */
    const STEP = 0.04;   // seconds between neighbours
    const CAP  = 0.2;    // no element waits longer than this, however long the batch

    const observer = new IntersectionObserver((entries, obs) => {
        entries
            .filter(entry => entry.isIntersecting)
            // Document order, so the cascade runs down the screen.
            .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
            .forEach((entry, i) => {
                entry.target.style.transitionDelay = `${Math.min(i * STEP, CAP)}s`;
                entry.target.classList.add('visible');
                obs.unobserve(entry.target);
            });
    }, { rootMargin: '120px 0px 160px 0px', threshold: 0.01 });

    animated.forEach(el => observer.observe(el));
});

/* ── The mobile nav ──
 * Which of strip and dropdown is on screen is the stylesheet's decision. This
 * only tracks open/closed, in one place: `aria-expanded` on the button. The CSS
 * draws from that attribute and a screen reader announces it, so there is no
 * second copy of the state. Above the breakpoint the button is display:none. */
function setUpNav() {
    const toggle = document.querySelector('.nav-toggle');
    const links  = document.getElementById('nav-links');
    if (!toggle || !links) return;

    const isOpen = () => toggle.getAttribute('aria-expanded') === 'true';

    function setOpen(open) {
        toggle.setAttribute('aria-expanded', String(open));
        links.classList.toggle('open', open);
    }

    toggle.addEventListener('click', () => setOpen(!isOpen()));

    // Escape hands the keyboard back to the button, not to a row that is gone.
    document.addEventListener('keydown', e => {
        if (e.key !== 'Escape' || !isOpen()) return;
        setOpen(false);
        toggle.focus();
    });

    // A tap anywhere else closes it.
    document.addEventListener('click', e => {
        if (!isOpen()) return;
        if (toggle.contains(e.target) || links.contains(e.target)) return;
        setOpen(false);
    });

    // Clear `.open` when the dropdown becomes the strip, or the menu reappears
    // pre-opened on the way back down. The crossing is detected by asking
    // whether the button is still drawn, so the breakpoint stays in the CSS.
    window.addEventListener('resize', () => {
        if (!isOpen()) return;
        if (getComputedStyle(toggle).display === 'none') setOpen(false);
    });
}
