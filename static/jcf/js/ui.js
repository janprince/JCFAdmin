/* JCF admin behaviours shared by every page. Loaded after Paces' app.js. */
(function () {
    'use strict';

    // Pages that create records in a modal re-render with the bound form when
    // it has errors. `data-jcf-open` on the modal re-opens it so the errors
    // are seen where the user typed.
    document.querySelectorAll('.modal[data-jcf-open]').forEach(function (el) {
        if (window.bootstrap) {
            window.bootstrap.Modal.getOrCreateInstance(el).show();
        }
    });

    // data-confirm="Question?" on a link or button asks before continuing;
    // on a form it asks before submitting.
    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('a[data-confirm], button[data-confirm]');
        if (trigger && !window.confirm(trigger.getAttribute('data-confirm'))) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (form.matches('form[data-confirm]') && !window.confirm(form.getAttribute('data-confirm'))) {
            event.preventDefault();
        }
    }, true);
})();

/* Foundation office interactions. No remote search or background writes. */
(function () {
    'use strict';
    const finder = document.getElementById('page-finder');
    if (finder) {
        const query = finder.querySelector('input');
        const results = finder.querySelector('.jcf-finder__results');
        const entries = Array.from(document.querySelectorAll('[data-page-name]')).map(link => ({
            title: link.dataset.pageName, group: link.dataset.pageGroup || 'Foundation', href: link.getAttribute('href'),
        }));
        const render = () => {
            const term = query.value.trim().toLowerCase();
            const matches = entries.filter(item => (item.title + ' ' + item.group).toLowerCase().includes(term));
            results.replaceChildren();
            matches.forEach(item => {
                const link = document.createElement('a'); link.href = item.href;
                const title = document.createElement('span'); title.textContent = item.title;
                const group = document.createElement('small'); group.textContent = item.group;
                link.append(title, group); results.append(link);
            });
            finder.querySelector('.jcf-finder__empty').hidden = matches.length > 0;
            finder.querySelector('[role="status"]').textContent = matches.length + (matches.length === 1 ? ' page found' : ' pages found');
        };
        const open = () => { if (!finder.open) { query.value = ''; render(); finder.showModal(); query.focus(); } };
        document.querySelectorAll('[data-finder-open]').forEach(button => {
            button.addEventListener('click', open);
            if (navigator.platform.toLowerCase().includes('mac')) button.querySelector('kbd').textContent = '⌘ K';
        });
        finder.querySelector('[data-finder-close]').addEventListener('click', () => finder.close());
        finder.addEventListener('click', event => { if (event.target === finder && (event.clientX < finder.getBoundingClientRect().left || event.clientX > finder.getBoundingClientRect().right || event.clientY < finder.getBoundingClientRect().top || event.clientY > finder.getBoundingClientRect().bottom)) finder.close(); });
        query.addEventListener('input', render);
        finder.addEventListener('keydown', event => {
            if (event.key === 'Escape') { event.preventDefault(); finder.close(); return; }
            const links = Array.from(results.querySelectorAll('a'));
            const index = links.indexOf(document.activeElement);
            if (event.key === 'ArrowDown') { event.preventDefault(); links[Math.min(index + 1, links.length - 1)]?.focus(); }
            if (event.key === 'ArrowUp') { event.preventDefault(); if (index <= 0) query.focus(); else links[index - 1].focus(); }
            if (event.key === 'Enter' && document.activeElement === query && links.length) { event.preventDefault(); links[0].click(); }
        });
        document.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); finder.open ? finder.close() : open(); } });
    }

    document.querySelectorAll('[data-password-toggle]').forEach(button => {
        const input = button.parentElement.querySelector('input');
        button.addEventListener('click', () => {
            const show = input.type === 'password'; input.type = show ? 'text' : 'password';
            button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
            button.setAttribute('aria-pressed', String(show));
            button.querySelector('i').className = 'ph ' + (show ? 'ph-eye-slash' : 'ph-eye');
        });
    });

    // Make overflowing tables keyboard-scrollable and explain the offscreen columns.
    document.querySelectorAll('.table-responsive').forEach((container, index) => {
        const hint = document.createElement('p'); hint.className = 'jcf-scroll-note';
        hint.id = 'table-scroll-note-' + index; hint.textContent = 'Scroll sideways to see all columns and actions.';
        container.before(hint);
        const update = () => {
            const overflow = container.scrollWidth > container.clientWidth + 1;
            hint.classList.toggle('is-needed', overflow);
            if (overflow) { container.tabIndex = 0; container.setAttribute('role', 'region'); container.setAttribute('aria-label', 'Records table'); container.setAttribute('aria-describedby', hint.id); }
            else { container.removeAttribute('tabindex'); container.removeAttribute('role'); container.removeAttribute('aria-label'); container.removeAttribute('aria-describedby'); }
        };
        new ResizeObserver(update).observe(container); update();
    });

    document.querySelectorAll('.jcf-field').forEach(field => {
        const control = field.querySelector('input:not([type=hidden]), select, textarea');
        if (!control) return;
        const descriptions = Array.from(field.querySelectorAll('.form-text[id], .jcf-field__error[id]')).map(item => item.id);
        if (descriptions.length) control.setAttribute('aria-describedby', descriptions.join(' '));
        if (field.querySelector('.jcf-field__error')) control.setAttribute('aria-invalid', 'true');
    });

    // Only full record editors get unsaved-change protection; GET filters do not.
    const editors = [];
    document.querySelectorAll('.jcf-form-actions').forEach(actions => {
        const form = actions.closest('form'); if (!form) return;
        const state = { dirty: false, submitted: false }; editors.push(state);
        const note = actions.querySelector('.jcf-form-status');
        const changed = () => { state.dirty = true; if (note) note.textContent = 'Unsaved changes'; };
        form.addEventListener('input', changed); form.addEventListener('change', changed);
        form.addEventListener('submit', event => { if (!event.defaultPrevented) { state.submitted = true; if (note) note.textContent = 'Saving changes…'; } });
        const invalid = form.querySelector('[aria-invalid="true"]');
        if (invalid) { if (note) note.textContent = 'Check the highlighted fields.'; invalid.focus(); }
    });
    window.addEventListener('beforeunload', event => {
        if (editors.some(state => state.dirty && !state.submitted)) { event.preventDefault(); event.returnValue = ''; }
    });
})();
