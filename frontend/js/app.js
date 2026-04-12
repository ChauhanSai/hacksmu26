/*
 * Analysis page orchestrator — loads JSON data and builds every card.
 */

const DATA_DIR = 'data';

// ── Date header ────────────────────────────────────────────────
document.getElementById('today').textContent = new Date().toLocaleDateString('en-US', {
  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
});

// ── Data loading helper ────────────────────────────────────────
async function loadJson(name) {
  try {
    const res = await fetch(`${DATA_DIR}/${name}`);
    if (!res.ok) throw new Error(`${name}: ${res.status}`);
    return await res.json();
  } catch (e) {
    console.warn(`Could not load ${name}:`, e.message);
    return null;
  }
}

function showNoData(id, msg = 'No data available — run the pipeline first.') {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div class="no-data">${msg}</div>`;
}

// ── Summary stat chips ─────────────────────────────────────────
function buildSummary(summary) {
  if (!summary) return;
  const bar = document.getElementById('summary-bar');
  const chips = [
    { label: 'Calls analyzed',     value: summary.n_calls,     sub: 'total vocalizations',
      explain: 'Total number of calls analyzed' },
    { label: 'Call types',         value: summary.n_clusters,  sub: 'GMM clusters',
      explain: 'Distinct acoustic call types found' },
    { label: 'Behaviors',          value: summary.n_contexts,  sub: 'observed contexts',
      explain: 'Different behaviors observed in data' },
    { label: 'Elephants',          value: summary.n_elephants, sub: 'unique callers',
      explain: 'Unique elephants in the dataset' },
  ];
  bar.innerHTML = chips.map(c => `
    <div class="stat-chip" data-explain="${c.explain}">
      <div class="label">${c.label}</div>
      <div class="value">${c.value ?? '—'}</div>
      <div class="sub">${c.sub}</div>
    </div>
  `).join('');
}

// ── Voice profiles table ───────────────────────────────────────
function buildVoiceTable(rows) {
  if (!rows || rows.length === 0) return showNoData('voice-table');
  const keys = Object.keys(rows[0]).filter(k => k !== 'elephant_id' && k !== 'n_calls');
  const header = `
    <tr>
      <th>Elephant</th><th>Calls</th>
      ${keys.map(k => `<th>${k}</th>`).join('')}
    </tr>`;
  const body = rows.map(r => `
    <tr>
      <td class="font-medium">${r.elephant_id}</td>
      <td>${r.n_calls}</td>
      ${keys.map(k => `<td>${typeof r[k] === 'number' ? r[k].toFixed(2) : (r[k] ?? '—')}</td>`).join('')}
    </tr>`).join('');
  document.getElementById('voice-table').innerHTML =
    `<table class="data-table"><thead>${header}</thead><tbody>${body}</tbody></table>`;
}

// ── Caller-context affinity table ──────────────────────────────
function buildAffinityTable(rows) {
  if (!rows || rows.length === 0) return showNoData('affinity-table');
  const body = rows.map(r => `
    <tr data-explain="This elephant's favorite behaviors">
      <td class="font-medium">${r.elephant_id}</td>
      <td>${r.n_calls}</td>
      <td class="text-[11px]">${r.top_contexts}</td>
      <td>${(r.deviation_chi2 ?? 0).toFixed(1)}</td>
      <td>${r.specialist ? '<span class="tag tag-orange">specialist</span>' : '<span class="tag tag-grey">generalist</span>'}</td>
    </tr>`).join('');
  document.getElementById('affinity-table').innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Elephant</th><th>N</th><th>Top contexts</th><th>χ²</th><th>Type</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>`;
}

// ── Sample interpretation cards (WHO/WHAT/WHY) ─────────────────
function tagClass(valence) {
  return { positive: 'tag-green', negative: 'tag-red', neutral: 'tag-teal' }[valence] || 'tag-grey';
}
function arousalTag(a) {
  return { high: 'tag-red', medium: 'tag-orange', low: 'tag-yellow' }[a] || 'tag-grey';
}

function buildInterpretations(rows) {
  if (!rows || rows.length === 0) return showNoData('interpretations');
  const html = rows.map(r => `
    <div class="interp-card" data-explain="A predicted interpretation for one call">
      <div class="interp-file">${r.filename}</div>
      <div class="text-[11px] text-[color:var(--text-2)] mb-1">
        Cluster <b>C${r.symbol}</b> · ${r.caller_age_sex}
      </div>
      <div class="interp-quote">"${r.interpretation}"</div>
      <div class="text-[11px] text-[color:var(--text-2)]">
        <b>${r.confidence}</b> confidence · ${r.alternative}
      </div>
      <div class="interp-meta">
        <span class="tag ${tagClass(r.valence)}">${r.valence}</span>
        <span class="tag ${arousalTag(r.arousal)}">${r.arousal} arousal</span>
        <span class="tag tag-purple">${r.top_context}</span>
      </div>
    </div>`).join('');
  document.getElementById('interpretations').innerHTML = html;
}

// ── CSV download buttons ───────────────────────────────────────
function wireDownloads() {
  document.querySelectorAll('.download-btn[data-csv]').forEach(btn => {
    btn.addEventListener('click', () => {
      const name = btn.getAttribute('data-csv');
      const a = document.createElement('a');
      a.href = `${DATA_DIR}/${name}`;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
    });
  });
}

// ── Main bootstrap ─────────────────────────────────────────────
(async function main() {
  wireDownloads();

  const [
    summary, clusters, pmi, transition, vowel, context,
    voiceProfiles, affinity, interpretations,
  ] = await Promise.all([
    loadJson('summary.json'),
    loadJson('clusters.json'),
    loadJson('pmi_matrix.json'),
    loadJson('transition_matrix.json'),
    loadJson('vowel_space.json'),
    loadJson('context_distribution.json'),
    loadJson('voice_profiles.json'),
    loadJson('caller_affinity.json'),
    loadJson('sample_interpretations.json'),
  ]);

  buildSummary(summary);

  if (clusters)        buildClusterChart('cluster-chart', clusters);
  else                 showNoData('cluster-chart');

  if (pmi)             buildPmiChart('pmi-chart', pmi);
  else                 showNoData('pmi-chart');

  if (transition)      buildTransitionChart('transition-chart', transition);
  else                 showNoData('transition-chart');

  if (vowel)           buildVowelChart('vowel-chart', vowel);
  else                 showNoData('vowel-chart');

  if (context)         buildContextChart('context-chart', context);
  else                 showNoData('context-chart');

  buildVoiceTable(voiceProfiles);
  buildAffinityTable(affinity);
  buildInterpretations(interpretations);
})();
