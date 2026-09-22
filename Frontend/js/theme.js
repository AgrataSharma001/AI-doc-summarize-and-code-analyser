window.DocodeTheme = (() => {
  let preference = 'system';
  try { preference = localStorage.getItem('docode-theme') || 'system'; } catch {}
  if (!['light', 'dark', 'system'].includes(preference)) preference = 'system';
  const media = matchMedia('(prefers-color-scheme: dark)');
  function apply() { document.documentElement.dataset.theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference; }
  media.addEventListener('change', apply); apply();
  return { get: () => preference, set(value) { if (!['light', 'dark', 'system'].includes(value)) return; preference = value; try { localStorage.setItem('docode-theme', value); } catch {} apply(); } };
})();
