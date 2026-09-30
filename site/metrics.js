'use strict';
(() => {
  if (navigator.doNotTrack === '1' || navigator.globalPrivacyControl) return;
  const source = (new URLSearchParams(location.search).get('utm_source') || '').slice(0, 80);
  let referrer = '';
  try { referrer = document.referrer ? new URL(document.referrer).origin : ''; } catch {}
  function send(kind, link = '') {
    const body = JSON.stringify({ kind, link, source, referrer });
    // Never delay or intercept navigation. No storage or visitor identifier.
    fetch('/metrics', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true, credentials: 'omit' }).catch(() => {});
  }
  let viewed = false;
  function view() { if (!viewed && document.visibilityState === 'visible') { viewed = true; send('view'); } }
  view(); document.addEventListener('visibilitychange', view);
  function click(e) { if (e.type === 'auxclick' && e.button !== 1) return; const a = e.target.closest('a[data-metric]'); if (a && e.isTrusted) send('click', a.dataset.metric); }
  document.addEventListener('click', click); document.addEventListener('auxclick', click);
})();
