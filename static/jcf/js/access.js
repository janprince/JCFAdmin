(() => {
  const select = document.querySelector('[data-role-form] select[name="role"]');
  if (!select) return;
  const render = () => document.querySelectorAll('[data-role-preview]').forEach(panel => {
    panel.hidden = panel.dataset.rolePreview !== select.value;
  });
  select.addEventListener('change', render);
  render();

  // A linked service member's units bound the roles on offer. The server
  // enforces this; here the choices simply follow the staff record picked.
  const worker = document.querySelector('[data-role-form] select[name="worker"]');
  const hint = document.querySelector('[data-service-hint]');
  const data = document.getElementById('service-roles');
  if (!worker || !hint || !data) return;
  const members = JSON.parse(data.textContent);
  const labels = JSON.parse(document.getElementById('role-labels').textContent);
  const original = { worker: worker.value, role: select.value };
  const limit = changed => {
    const member = members[worker.value];
    const allowed = member && member.roles;
    // An existing account keeps its saved role selectable until the link changes.
    const keep = worker.value === original.worker ? original.role : null;
    Array.from(select.options).forEach(option => {
      option.disabled = Boolean(allowed) && !allowed.includes(option.value) && option.value !== keep;
    });
    if (!allowed) { hint.hidden = true; return; }
    hint.hidden = false;
    hint.textContent = allowed.length
      ? `${member.units.join(', ')} allow${member.units.length === 1 ? 's' : ''}: ${allowed.map(role => labels[role]).join(', ')}.`
      : `${member.units.join(', ')} ${member.units.length === 1 ? 'works' : 'work'} outside the portal. An Admin can allow a role on the unit first.`;
    if (changed && allowed.length && select.selectedOptions[0].disabled) {
      select.value = allowed[0];
      render();
    }
  };
  worker.addEventListener('change', () => limit(true));
  limit(false);
})();
