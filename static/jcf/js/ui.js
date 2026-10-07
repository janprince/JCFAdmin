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

    // The whole row opens its record, like the link in its first cell.
    document.querySelectorAll('table.jcf-table').forEach(table => {
        table.querySelectorAll(':scope > tbody > tr').forEach(row => {
            const primary = row.cells[0] && row.cells[0].querySelector('a[href]:not([href^="#"])');
            if (primary) { row.classList.add('jcf-row-link'); row.dataset.href = primary.href; }
        });
        table.addEventListener('click', event => {
            const row = event.target.closest('tr.jcf-row-link');
            if (!row || event.target.closest('a, button, input, select, textarea, label, .dropdown, [data-bs-toggle]')) return;
            if (String(window.getSelection())) return;
            if (event.metaKey || event.ctrlKey) window.open(row.dataset.href, '_blank', 'noopener');
            else window.location.href = row.dataset.href;
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

/* data-copy="text" on a button copies the text. A [data-copy-label] inside
   it reads "Copied" for a moment; data-copy-done names what was copied for
   screen readers. Shared by digital resources and the booking-form link. */
(function () {
    'use strict';
    const live = document.createElement('p');
    live.className = 'visually-hidden';
    live.setAttribute('aria-live', 'polite');
    document.body.append(live);

    // The clipboard API can be refused (plain http, embedded browsers), so
    // fall back to the older copy command before giving up.
    const legacyCopy = text => {
        const area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.append(area);
        area.select();
        let ok = false;
        try { ok = document.execCommand('copy'); } catch (error) { ok = false; }
        area.remove();
        return ok;
    };
    const copyText = async text => {
        try {
            await navigator.clipboard.writeText(text);
        } catch (error) {
            if (!legacyCopy(text)) throw error;
        }
    };
    // Last resort: select the address on screen so Ctrl+C / Cmd+C copies it.
    const selectTarget = button => {
        const target = button.dataset.copySelect ? document.querySelector(button.dataset.copySelect)
            : button.closest('[data-resource]')?.querySelector('.jcf-resource__url');
        if (!target) return false;
        window.getSelection().selectAllChildren(target);
        return true;
    };

    document.addEventListener('click', async event => {
        const button = event.target.closest('[data-copy]');
        if (!button) return;
        const label = button.querySelector('[data-copy-label]');
        const icon = button.querySelector('i');
        if (label && !label.dataset.original) label.dataset.original = label.textContent;
        if (icon && !icon.dataset.original) icon.dataset.original = icon.className;
        const restore = delay => {
            clearTimeout(button.copyTimer);
            button.copyTimer = setTimeout(() => {
                if (label) label.textContent = label.dataset.original;
                if (icon) icon.className = icon.dataset.original;
                button.classList.remove('is-copied');
            }, delay);
        };
        try {
            await copyText(button.dataset.copy);
            live.textContent = (button.dataset.copyDone || 'Copied') + '.';
            if (label) label.textContent = 'Copied';
            if (icon) icon.className = 'ph ph-check';
            button.classList.add('is-copied');
            restore(1800);
        } catch (error) {
            const keys = navigator.platform.toLowerCase().includes('mac') ? '⌘C' : 'Ctrl+C';
            const selected = selectTarget(button);
            live.textContent = selected ? `This browser blocked copying. The text is selected — press ${keys}.`
                : 'This browser blocked copying.';
            if (label && selected) { label.textContent = `Press ${keys}`; restore(4000); }
        }
    });
})();
