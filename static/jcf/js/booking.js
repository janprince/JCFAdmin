/* Public booking form: show only what applies, and name the day they were born. */
(() => {
  const form = document.querySelector('[data-booking-form]');
  if (!form) return;
  const errors = form.querySelector('[data-booking-errors]');
  if (errors) errors.focus();

  const unknown = form.querySelector('input[name="dob_unknown"]');
  const known = form.querySelector('[data-dob-known]');
  const dayPicker = form.querySelector('[data-dob-unknown]');
  const born = form.querySelector('input[name="date_of_birth"]');
  const weekday = form.querySelector('[data-weekday]');
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

  const showDob = () => {
    known.hidden = unknown.checked;
    dayPicker.hidden = !unknown.checked;
  };
  const showWeekday = () => {
    const [y, m, d] = (born.value || '').split('-').map(Number);
    // Noon UTC avoids the date shifting across time zones.
    weekday.textContent = y > 1900 && m && d ? `You were born on a ${days[new Date(Date.UTC(y, m - 1, d, 12)).getUTCDay()]}.` : '';
  };
  unknown.addEventListener('change', showDob);
  born.addEventListener('input', showWeekday);
  showDob();
  showWeekday();

  const heard = form.querySelector('select[name="heard_from"]');
  const detail = form.querySelector('[data-heard-detail]');
  const showDetail = () => { detail.hidden = !heard.value; };
  heard.addEventListener('change', showDetail);
  showDetail();

  form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = 'Sending…';
  });
})();
