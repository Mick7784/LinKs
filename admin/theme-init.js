// Load before styles so the selected admin theme is applied without inline scripts.
try {
  const mode=localStorage.getItem('links-admin-theme')||'dark';
  document.documentElement.dataset.theme=mode==='light'||mode==='dark'?mode:matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';
} catch { document.documentElement.dataset.theme='dark'; }
