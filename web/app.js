'use strict';
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const show = (el, html) => { el.innerHTML = html; };
const err = (m) => `<p class="err" role="alert">${esc(m)}</p>`;

// Turn a failed response into a readable message (handles FastAPI 422 detail arrays).
async function errorText(res) {
  let body = null;
  try { body = await res.json(); } catch (_) { /* not JSON */ }
  const d = body && body.detail;
  if (Array.isArray(d)) {
    return d.map((e) => (e.loc ? e.loc.filter((x) => x !== 'body').join('.') + ': ' : '') + (e.msg || JSON.stringify(e))).join('; ');
  }
  if (d) return typeof d === 'string' ? d : JSON.stringify(d);
  return `Request failed (${res.status} ${res.statusText})`;
}

async function api(path, opts) {
  let res;
  try { res = await fetch(path, opts); }
  catch (e) { throw new Error('Network error: ' + e.message); }
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

async function run(form, out, fn) {
  const btn = form.querySelector('button');
  btn.disabled = true;
  show(out, '<p class="muted">Loading&hellip;</p>');
  try { show(out, await fn()); }
  catch (e) { show(out, err(e.message)); }
  finally { btn.disabled = false; }
}

// Accept either an Envelope ({attributes}) or a flat object.
const attrs = (r) => (r && r.attributes) || r || {};

// Status bar
(async () => {
  const el = $('status');
  try {
    const h = await api('/health');
    el.className = 'ok';
    el.textContent = 'API: ' + (h.status || 'ok');
  } catch (e) {
    el.className = 'bad';
    el.textContent = 'API unreachable: ' + e.message;
  }
})();

// Panel 1: tariff lookup
$('tariff-form').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const hs = $('t-hs').value.replace(/[\s.]/g, '');
  run(ev.target, $('tariff-out'), async () => {
    const a = attrs(await api('/tariff/' + encodeURIComponent(hs)));
    const rates = a.rates || [];
    const rows = rates.length
      ? rates.map((r) => `<tr><td>${esc(r.treatment)}</td><td>${esc(r.rate)}</td></tr>`).join('')
      : '<tr><td colspan="2" class="muted">No rates listed</td></tr>';
    return `<dl><dt>HS code</dt><dd>${esc(a.hs_code)}</dd>
      <dt>Description</dt><dd>${esc(a.description)}</dd>
      <dt>Effective from</dt><dd>${esc(a.effective_from || '-')}</dd>
      <dt>Effective to</dt><dd>${esc(a.effective_to || 'open-ended')}</dd></dl>
      <table><thead><tr><th>Treatment</th><th>Rate</th></tr></thead><tbody>${rows}</tbody></table>`;
  });
});

// Panel 2: landed cost
const money = (v) => {
  if (v && typeof v === 'object') return `${esc(v.amount)} ${esc(v.currency || '')}`;
  return esc(v);
};
$('c-ship').value = new Date().toISOString().slice(0, 10);
$('cost-form').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const body = {
    hs_code: $('c-hs').value.replace(/[\s.]/g, ''),
    origin_country: $('c-origin').value.trim().toUpperCase(),
    declared_value: { amount: Number($('c-amount').value), currency: $('c-currency').value.trim().toUpperCase() || 'CAD' },
    treatment: $('c-treatment').value.trim() || 'MFN',
    shipment_date: $('c-ship').value,
  };
  body.jurisdiction = $('c-jur').value;
  if ($('c-fta').value !== '') body.fta_qualified = $('c-fta').value === 'true';
  if ($('c-mode').value) body.mode = $('c-mode').value;
  if ($('c-qty').value !== '') body.quantity = Number($('c-qty').value);
  if ($('c-unit').value.trim()) body.unit = $('c-unit').value.trim();
  run(ev.target, $('cost-out'), async () => {
    const res = await fetch('/landed-cost', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (res.status === 409) {
      const p = await res.json();
      const link = /^https?:\/\//.test(p.source_url || '')
        ? ` <a href="${esc(p.source_url)}" rel="noopener noreferrer">source</a>` : '';
      return `<div class="err" role="alert"><strong>Prohibited</strong>
        <p>${esc(p.message)}</p>
        <p>List ${esc(p.list_id)} (${esc(p.jurisdiction)}, origin ${esc(p.origin_country)}, HS ${esc(p.hs_code)});
        effective ${esc(p.effective_from)}${p.effective_to ? ' to ' + esc(p.effective_to) : ''}.${link}</p></div>`;
    }
    if (res.status === 501) return `<p class="muted" role="status">${esc(await errorText(res))}</p>`;
    if (!res.ok) throw new Error(await errorText(res));
    const r = await res.json();
    const comps = r.components || [];
    const fxLine = comps.find((c) => c.startsWith('FX '));
    const surLine = comps.find((c) => c.startsWith('surtax '));
    return `<dl><dt>Value in CAD</dt><dd>${money({ amount: r.value_cad, currency: 'CAD' })}</dd>
      ${fxLine ? `<dt>Exchange rate</dt><dd>${esc(fxLine)}</dd>` : ''}
      <dt>Rate</dt><dd>${esc(r.rate)}</dd>
      <dt>Effective duty rate</dt><dd>${esc(r.duty_rate)}%</dd>
      <dt>Duty</dt><dd>${money({ amount: r.duty, currency: 'CAD' })}</dd>
      <dt>Surtax</dt><dd>${surLine ? esc(surLine) : 'none'}</dd>
      <dt>Total</dt><dd><strong>${money({ amount: r.total, currency: 'CAD' })}</strong></dd>
      ${r.total_if_fta_qualified != null ? `<dt>Total if FTA qualified</dt><dd><strong>${money({ amount: r.total_if_fta_qualified, currency: 'CAD' })}</strong> (surtax ${esc(r.surtax_if_fta_qualified)})</dd>` : ''}</dl>
      ${comps.length ? '<ul class="muted">' + comps.map((c) => `<li>${esc(c)}</li>`).join('') + '</ul>' : ''}
      <p class="muted">GST/PST are not included. Surtax remissions and exclusions are not modelled.</p>`;
  });
});

// Panel 3: tender search
$('tender-form').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const q = $('s-q').value.trim();
  const level = $('s-level').value;
  run(ev.target, $('tender-out'), async () => {
    const params = new URLSearchParams({ type: 'tender', limit: '50' });
    if (q) params.set('q', q);
    const data = await api('/records?' + params);
    let list = Array.isArray(data) ? data : (data.items || data.records || data.results || []);
    // The API has no buyer-level filter; apply it client-side.
    if (level) list = list.filter((r) => ((attrs(r).buyer || {}).level) === level);
    if (!list.length) return '<p class="muted">No tenders found.</p>';
    return '<ul class="cards">' + list.map((r) => {
      const a = attrs(r);
      const v = a.value_estimate;
      const url = typeof a.url === 'string' && /^https?:\/\//i.test(a.url) ? a.url : '';
      return `<li class="card"><h3>${esc(a.title)}</h3>
        <p>Buyer: ${esc((a.buyer || {}).name || '-')}${(a.buyer || {}).level ? ' (' + esc(a.buyer.level) + ')' : ''}</p>
        <p>Closes: ${esc(a.closes_at || '-')}</p>
        <p>Value: ${v ? money(v) : '-'}</p>
        ${url ? `<p><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">View notice</a></p>` : ''}</li>`;
    }).join('') + '</ul>';
  });
});
