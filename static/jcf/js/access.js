(() => {
  const select = document.querySelector('[data-role-form] select[name="role"]');
  if (!select) return;
  const render = () => document.querySelectorAll('[data-role-preview]').forEach(panel => {
    panel.hidden = panel.dataset.rolePreview !== select.value;
  });
  select.addEventListener('change', render);
  render();
})();
