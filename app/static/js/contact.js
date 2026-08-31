document.addEventListener('DOMContentLoaded', () => {
    const trigger = document.getElementById('email-trigger');
    const picker  = document.getElementById('email-picker');
    const copyBtn = document.getElementById('email-copy-btn');

    if (!trigger || !picker) return;

    const email = trigger.dataset.email;

    document.getElementById('opt-gmail').href =
        `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(email)}`;
    document.getElementById('opt-outlook').href =
        `https://outlook.live.com/mail/0/deeplink/compose?to=${encodeURIComponent(email)}`;
    document.getElementById('opt-default').href = `mailto:${email}`;

    function open() {
        picker.hidden = false;
        trigger.classList.add('open');
        trigger.setAttribute('aria-expanded', 'true');
    }

    function close() {
        picker.hidden = true;
        trigger.classList.remove('open');
        trigger.setAttribute('aria-expanded', 'false');
    }

    trigger.addEventListener('click', () => picker.hidden ? open() : close());

    trigger.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); picker.hidden ? open() : close(); }
        if (e.key === 'Escape') close();
    });

    document.addEventListener('click', e => {
        if (!trigger.contains(e.target) && !picker.contains(e.target)) close();
    });

    picker.querySelectorAll('.email-option').forEach(opt => {
        opt.addEventListener('click', close);
    });

    copyBtn.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(email);
            copyBtn.textContent = 'Copied!';
            copyBtn.classList.add('copied');
        } catch {
            copyBtn.textContent = email;
        }
        setTimeout(() => {
            copyBtn.textContent = 'Copy email address';
            copyBtn.classList.remove('copied');
        }, 2000);
    });
});
