/* Digital resources: copy, share and find links without leaving the page. */
(() => {
  const page = document.querySelector('[data-resources]');
  if (!page) return;

  // The phone's share sheet (WhatsApp, SMS, email) where the browser has one.
  if (navigator.share) {
    page.querySelectorAll('[data-share]').forEach(button => {
      button.hidden = false;
      button.addEventListener('click', () => {
        navigator.share({ title: button.dataset.shareTitle, url: button.dataset.share }).catch(() => {});
      });
    });
  }

  const filter = page.querySelector('[data-resource-filter]');
  if (!filter) return;
  const count = page.querySelector('[data-resource-count]');
  const none = page.querySelector('[data-resource-none]');
  const groups = Array.from(page.querySelectorAll('[data-resource-group]'));
  filter.addEventListener('input', () => {
    const words = filter.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    groups.forEach(group => {
      let inGroup = 0;
      group.querySelectorAll('[data-resource]').forEach(row => {
        const text = row.dataset.search.toLowerCase();
        const match = words.every(word => text.includes(word));
        row.hidden = !match;
        if (match) inGroup += 1;
      });
      group.hidden = inGroup === 0;
      shown += inGroup;
    });
    none.hidden = shown > 0;
    count.textContent = words.length ? `${shown} link${shown === 1 ? '' : 's'}` : '';
  });
})();
