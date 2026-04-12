/*
 * Explain mode — toggles simple hover descriptions for every labeled element.
 *
 * Any element with data-explain="..." gets a floating tooltip when
 * explain mode is on. In explain mode Plotly charts also swap their
 * hover templates to a simplified one-liner (set via Chart helpers).
 */

const EXPLAIN = (() => {
  let on = false;
  const tooltip = document.getElementById('explain-tooltip');
  const btn = document.getElementById('explain-btn');
  const banner = document.getElementById('explain-banner');

  if (!btn) {
    return { isOn: () => false, hide: () => {} };
  }

  function setEnabled(v) {
    on = v;
    document.body.classList.toggle('explain-mode', on);
    banner.classList.toggle('hidden', !on);
    btn.textContent = on ? '💡 Explaining…' : '💡 Explain';
    // Nudge Plotly traces to rerender their hover templates if they care.
    document.dispatchEvent(new CustomEvent('explain-toggle', { detail: { on } }));
    if (!on) hideTip();
  }

  function showTip(e, text) {
    if (!on || !text) return;
    tooltip.textContent = text;
    tooltip.classList.remove('hidden');
    positionTip(e);
  }

  function positionTip(e) {
    const pad = 14;
    const rect = tooltip.getBoundingClientRect();
    let x = e.clientX + pad;
    let y = e.clientY + pad;
    if (x + rect.width  > window.innerWidth)  x = e.clientX - rect.width  - pad;
    if (y + rect.height > window.innerHeight) y = e.clientY - rect.height - pad;
    tooltip.style.left = `${x}px`;
    tooltip.style.top  = `${y}px`;
  }

  function hideTip() {
    tooltip.classList.add('hidden');
  }

  // Click button → toggle
  btn.addEventListener('click', () => setEnabled(!on));

  // Global hover handler (event delegation)
  document.addEventListener('mouseover', (e) => {
    if (!on) return;
    const el = e.target.closest('[data-explain]');
    if (!el) return hideTip();
    showTip(e, el.getAttribute('data-explain'));
  });
  document.addEventListener('mousemove', (e) => {
    if (!on || tooltip.classList.contains('hidden')) return;
    positionTip(e);
  });
  document.addEventListener('mouseout', (e) => {
    if (!on) return;
    const el = e.target.closest('[data-explain]');
    if (!el || !el.contains(e.relatedTarget)) hideTip();
  });

  return {
    isOn: () => on,
    hide: hideTip,
  };
})();
