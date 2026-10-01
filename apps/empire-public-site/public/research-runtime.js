/* First-party observations only. No cookies, local storage, inferred identity or outbound. */
(() => {
  const form = document.querySelector('#research-enquiry');
  if (!(form instanceof HTMLFormElement)) return;
  const fields = new FormData(form);
  const campaign_id = fields.get('campaign_id');
  const asset_id = fields.get('asset_id');
  const status = document.querySelector('#receipt');
  const observe = (event_type) => fetch('/api/research/event', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin',
    body: JSON.stringify({event_id: crypto.randomUUID(), event_type, campaign_id, asset_id,
      source: 'owned_site', channel: 'organic', occurred_at: new Date().toISOString()})
  }).catch(() => {});
  observe('campaign_page_view');
  let started = false;
  form.addEventListener('input', () => {
    if (!started) { started = true; observe('campaign_enquiry_started'); }
  });
  form.querySelector('button').addEventListener('click', () => observe('campaign_cta_click'));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const button = form.querySelector('button');
    button.disabled = true;
    status.textContent = 'Submitting enquiry…';
    try {
      const response = await fetch('/api/research/enquiry', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin',
        body: JSON.stringify(Object.fromEntries(new FormData(form)))
      });
      const receipt = await response.json();
      if (!response.ok || receipt.accepted !== true) throw new Error('not accepted');
      status.textContent = 'Enquiry received. You have not been subscribed to marketing.';
      // The server atomically records campaign_enquiry_submitted with the receipt.
      form.reset();
    } catch (_) {
      status.textContent = 'Your enquiry could not be confirmed. Please try again; identical submissions are deduplicated.';
    } finally { button.disabled = false; }
  });
})();
