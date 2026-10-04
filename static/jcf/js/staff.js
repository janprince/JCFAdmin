/* Service team form: show only the fields that apply to the choices made. */
(() => {
  const form = document.querySelector('[data-service-form]');
  if (!form) return;

  const toggle = (selector, visible) => form.querySelectorAll(selector).forEach(panel => {
    panel.hidden = !visible;
  });

  // Who is serving: an existing contact, or a new person.
  const person = form.querySelectorAll('input[name="person"]');
  const showPerson = () => {
    const value = (Array.from(person).find(input => input.checked) || {}).value || 'existing';
    form.querySelectorAll('[data-person-panel]').forEach(panel => { panel.hidden = panel.dataset.personPanel !== value; });
  };
  person.forEach(input => input.addEventListener('change', showPerson));
  if (person.length) showPerson();

  // A type-to-narrow box above the contact list. Contacts can run to the
  // thousands, so the list is filtered in place rather than scrolled.
  form.querySelectorAll('[data-picker-filter]').forEach(input => {
    const select = document.getElementById(input.dataset.pickerFilter);
    const count = form.querySelector('[data-picker-count]');
    const options = Array.from(select.options).filter(option => option.value);
    // As an open list, the "Choose a contact" placeholder would read as a row.
    Array.from(select.options).filter(option => !option.value).forEach(option => { option.hidden = true; });
    select.size = Math.min(7, Math.max(options.length, 2));
    const render = () => {
      const term = input.value.trim().toLowerCase();
      let shown = 0;
      options.forEach(option => {
        const match = !term || option.text.toLowerCase().includes(term);
        option.hidden = !match;
        if (match) shown += 1;
      });
      if (count) count.textContent = term ? `${shown} match${shown === 1 ? '' : 'es'}.` : '';
      if (term && shown === 1) select.value = options.find(option => !option.hidden).value;
    };
    input.addEventListener('input', render);
    input.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown') { event.preventDefault(); select.focus(); }
      if (event.key === 'Enter') event.preventDefault();
    });
  });

  // Service ended date only matters once someone is inactive.
  const status = form.querySelector('select[name="status"]');
  const showEnded = () => toggle('[data-ended-panel]', status.value === 'inactive');
  status.addEventListener('change', showEnded);
  showEnded();

  // Amount and currency only when they receive an allowance.
  const allowance = form.querySelector('input[name="receives_allowance"]');
  const amount = form.querySelector('input[name="allowance"]');
  const showAllowance = () => {
    toggle('[data-allowance-panel]', allowance.checked);
    if (allowance.checked && document.activeElement === allowance && !amount.value) amount.focus();
  };
  allowance.addEventListener('change', showAllowance);
  showAllowance();

  // The main unit is not also a unit they "also serve in".
  const unit = form.querySelector('select[name="unit"]');
  const others = form.querySelectorAll('input[name="other_units"]');
  const syncUnits = () => others.forEach(box => {
    const main = box.value === unit.value;
    box.disabled = main;
    if (main) box.checked = false;
    box.closest('label').classList.toggle('is-disabled', main);
  });
  unit.addEventListener('change', syncUnits);
  syncUnits();
})();
