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

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Matches CLUSTER_COLORS in charts.js (neighbor card accents) */
const KNN_CLUSTER_COLORS = ['#5eead4', '#34d399', '#fbbf24', '#f87171', '#fb7185', '#a78bfa'];

const FI_CATEGORY_FALLBACK = {
  Temporal: {
    explain_title: 'Temporal dynamics',
    explain_detail: 'This feature summarizes how the call evolves over short time windows in the fingerprint.',
    explain_why: 'Context often shows up in onset, sustain, and decay. Temporal coefficients therefore rank high in gradient boosting splits.',
  },
  Tremor: {
    explain_title: 'Modulation / tremor',
    explain_detail: 'Low-frequency amplitude or frequency modulation tied to laryngeal and trunk mechanics.',
    explain_why: 'Tremor characteristics differ between calm and aroused states, so the model uses them to refine boundaries between classes.',
  },
  Rumble: {
    explain_title: 'Infrasonic rumble structure',
    explain_detail: 'Energy and shape within the elephant rumble frequency band used for long-range signaling.',
    explain_why: 'Much of the behavioral signal in this dataset lives below human hearing; rumble-band features carry the strongest species-specific cues.',
  },
  Timbre: {
    explain_title: 'Voice timbre / spectral shape',
    explain_detail: 'Mel-based descriptors of texture, analogous to what makes two human voices sound different.',
    explain_why: 'Timbre separates overlapping contexts when duration and coarse pitch look alike — the model uses it as a fine discriminator.',
  },
  Harmonic: {
    explain_title: 'Harmonic organization',
    explain_detail: 'Regularity and spacing of harmonic partials in the low spectrum.',
    explain_why: 'Harmonic structure reflects vocal effort and nonlinear phenomena; the classifier exploits this for high-arousal vs steady calls.',
  },
};

function renderGraphKnnSummary(clustersJson, neighbors) {
  const el = document.getElementById('graph-knn-summary');
  if (!el || !neighbors?.length) {
    if (el) el.innerHTML = '';
    return;
  }

  const beh = new Map();
  const clCount = new Map();
  neighbors.forEach(n => {
    const b = n.context || 'Unknown';
    beh.set(b, (beh.get(b) || 0) + 1);
    clCount.set(n.cluster, (clCount.get(n.cluster) || 0) + 1);
  });

  const clRows = clustersJson.clusters || [];
  const nBeh = beh.size;
  const nCl = clCount.size;

  const neighborTitle = escapeHtml(
    `${neighbors.length} corpus calls with the shortest duration distance to your recording`,
  );
  const neighborCircle = `
    <div class="knn-sum-circle knn-sum-circle--neighbors" title="${neighborTitle}">
      <span class="knn-sum-circle__n mono">${neighbors.length}</span>
      <span class="knn-sum-circle__t">neighbors</span>
      <span class="knn-sum-circle__s">shortest duration in corpus</span>
    </div>`;

  const behCircles = [...beh.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => {
      const full = escapeHtml(k);
      const count = escapeHtml(String(v));
      return `<div class="knn-sum-circle knn-sum-circle--beh" title="${full} (${count} of ${neighbors.length})">
        <span class="knn-sum-circle__beh">${full}</span>
        <span class="knn-sum-circle__n mono">${count}</span>
        <span class="knn-sum-circle__s">of ${neighbors.length}</span>
      </div>`;
    })
    .join('');

  const clCircles = [...clCount.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([cid, v]) => {
      const col = KNN_CLUSTER_COLORS[Number(cid) % KNN_CLUSTER_COLORS.length];
      const row = clRows.find(c => c.id === cid);
      const top = row?.top_context ? String(row.top_context) : '';
      const topEsc = escapeHtml(top);
      const title = escapeHtml(`Cluster C${cid}, ${v} neighbor(s)${top ? ` — ${top}` : ''}`);
      return `<div class="knn-sum-circle knn-sum-circle--cl" style="--knn-ring:${col}" title="${title}">
        <span class="knn-sum-circle__cl mono">C${cid}</span>
        <span class="knn-sum-circle__n mono">${v}</span>
        ${top ? `<span class="knn-sum-circle__ctx">${topEsc}</span>` : ''}
      </div>`;
    })
    .join('');

  el.innerHTML = `
    <div class="knn-summary-strip" role="region" aria-label="KNN neighbor distribution">
      <div class="knn-sum-col">
        <span class="knn-sum-heading">Neighbors</span>
        <div class="knn-sum-circles">${neighborCircle}</div>
      </div>
      <span class="knn-sum-sep" aria-hidden="true"></span>
      <div class="knn-sum-col knn-sum-col--wide">
        <span class="knn-sum-heading">Behaviors <span class="knn-sum-heading__n">(${nBeh})</span></span>
        <div class="knn-sum-circles">${behCircles}</div>
      </div>
      <span class="knn-sum-sep" aria-hidden="true"></span>
      <div class="knn-sum-col knn-sum-col--wide">
        <span class="knn-sum-heading">Clusters <span class="knn-sum-heading__n">(${nCl})</span></span>
        <div class="knn-sum-circles">${clCircles}</div>
      </div>
    </div>`;
}

function renderGraphKnnNarrative(clusters, audioData, knn) {
  const el = document.getElementById('graph-knn-narrative');
  if (!el) return;

  const { neighbors, dur } = knn;
  const cl = clusters.clusters || [];
  renderGraphKnnSummary(clusters, neighbors);

  el.innerHTML = neighbors.map((n, i) => {
    const delta = Math.abs(Number(n.duration) - dur);
    const clusterRow = cl.find(c => c.id === n.cluster) || cl[n.cluster];
    const topCtx = clusterRow?.top_context || n.context;
    const f0 = typeof n.mean_f0 === 'number' ? `${n.mean_f0.toFixed(0)} Hz` : '—';
    const fn = escapeHtml(n.filename || `Neighbor ${i + 1}`);
    const ctx = escapeHtml(n.context || '—');
    const caller = escapeHtml(n.age_sex || '—');
    const sound = escapeHtml(n.sound_type || '—');
    const topCtxH = escapeHtml(String(topCtx));
    const accent = KNN_CLUSTER_COLORS[n.cluster % KNN_CLUSTER_COLORS.length];

    const descLine1 = `C${n.cluster} · ${topCtxH} · ${Number(n.duration).toFixed(2)}s · F0 ${f0}`;
    const descLine2 = `${ctx} · ${caller} · ${sound}`;

    const whyText =
      `Your clip is ${dur.toFixed(2)}s; this call is ${delta.toFixed(2)}s away in length (KNN pick). ` +
      `Same UMAP neighborhood as other duration-matched rumbles.`;

    return `
      <article class="knn-neighbor-card" style="--knn-accent:${accent}">
        <div class="knn-card-top">
          <span class="knn-idx">#${i + 1}</span>
          <div class="knn-filename" title="${fn}">${fn}</div>
        </div>
        <div class="knn-pills">
          <span class="knn-pill knn-pill-accent" style="--knn-accent:${accent}">C${n.cluster}</span>
          <span class="knn-pill" style="border-color:${accent}55;color:var(--text-1)">${ctx}</span>
        </div>
        <div class="knn-block">
          <span class="knn-k">Record</span>
          <div class="knn-v">${descLine1}</div>
        </div>
        <div class="knn-block">
          <span class="knn-k">Labels</span>
          <div class="knn-v">${descLine2}</div>
        </div>
        <div class="knn-block">
          <span class="knn-k">Similarity</span>
          <div class="knn-v">${whyText}</div>
        </div>
      </article>`;
  }).join('');
}

function wireGraphAnalysisSection(clusters, audioData) {
  const section = document.getElementById('graph-analysis-section');
  const lede = document.getElementById('graph-analysis-lede');
  if (!section || !lede) return;

  section.classList.remove('hidden');
  const orig = audioData.original_name || 'your recording';
  const dur = parseFloat(audioData.duration_seconds) || 0;
  lede.innerHTML =
    `Recording <strong style="color:var(--text-0)">${escapeHtml(orig)}</strong> (${dur.toFixed(2)}s) &mdash; ` +
    'the star and ringed dots sit on the <strong style="color:var(--text-0)">Repertoire Atlas</strong> above (one shared UMAP). Neighbors = five shortest duration gaps in the corpus.';

  const sumEl = document.getElementById('graph-knn-summary');
  const railEl = document.getElementById('graph-knn-narrative');

  if (!clusters) {
    if (sumEl) sumEl.innerHTML = '';
    if (railEl) railEl.innerHTML = '';
    lede.textContent =
      'Cluster JSON missing — run the linguistics pipeline so data/clusters.json exists; the map above cannot show your overlay until then.';
    return;
  }

  const knn = getDurationKnnNeighbors(clusters, audioData, 5);
  if (knn) renderGraphKnnNarrative(clusters, audioData, knn);
  else {
    if (sumEl) sumEl.innerHTML = '<span style="color:var(--risk-crit)">No duration-tagged calls to match.</span>';
    if (railEl) railEl.innerHTML = '';
  }
}

function wireGraphAnalysisEmpty(message) {
  const section = document.getElementById('graph-analysis-section');
  const lede = document.getElementById('graph-analysis-lede');
  if (!section || !lede) return;
  section.classList.remove('hidden');
  lede.textContent = message;
  const sumEl = document.getElementById('graph-knn-summary');
  const railEl = document.getElementById('graph-knn-narrative');
  if (sumEl) {
    sumEl.innerHTML =
      '<span class="no-data" style="display:inline">Open Cleanup → process a WAV → Analyze → use <b>Graph analysis</b> on the report.</span>';
  }
  if (railEl) railEl.innerHTML = '';
}

function wireFeatureImportanceModal(modelInsights) {
  const gd = document.getElementById('feature-importance-chart');
  const root = document.getElementById('fi-modal-root');
  if (!gd || !root || !modelInsights?.top_features?.length) return;

  const heading = document.getElementById('fi-modal-heading');
  const meta = document.getElementById('fi-modal-meta');
  const detail = document.getElementById('fi-modal-detail');
  const why = document.getElementById('fi-modal-why');
  const closeBtn = document.getElementById('fi-modal-close');

  function closeModal() {
    root.classList.add('hidden');
    root.setAttribute('aria-hidden', 'true');
  }

  function openForFeature(name) {
    const feat = modelInsights.top_features.find(f => f.name === name);
    if (!feat) return;

    const fb = FI_CATEGORY_FALLBACK[feat.category] || FI_CATEGORY_FALLBACK.Timbre;
    const title = feat.explain_title || feat.name;
    const body = feat.explain_detail || fb.explain_detail;
    const whyText = feat.explain_why || fb.explain_why;

    heading.textContent = title;
    meta.textContent = `${feat.name} · ${feat.category} · ${(feat.importance * 100).toFixed(1)}% importance`;
    detail.textContent = body;
    why.innerHTML =
      '<strong style="color:var(--text-0)">Why it matters for prediction</strong><br>' +
      `<span style="color:var(--text-1)">${escapeHtml(whyText)}</span>`;

    root.classList.remove('hidden');
    root.setAttribute('aria-hidden', 'false');
  }

  gd.on('plotly_click', (ev) => {
    const pt = ev.points && ev.points[0];
    if (!pt || typeof pt.y !== 'string') return;
    openForFeature(pt.y);
  });

  closeBtn.addEventListener('click', closeModal);
  root.addEventListener('click', (e) => {
    if (e.target === root) closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !root.classList.contains('hidden')) closeModal();
  });
}

// ── Main bootstrap ─────────────────────────────────────────────
(async function main() {
  wireDownloads();

  const [
    summary, clusters, pmi, transition, vowel, context,
    voiceProfiles, affinity, interpretations, modelInsights,
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
    loadJson('model_insights.json'),
  ]);

  buildSummary(summary);

  const graphMode = new URLSearchParams(window.location.search).get('graph') === '1';
  const sessionAudio = graphMode
    ? (sessionStorage.getItem('elephantAudioData') || localStorage.getItem('elephantAudioData'))
    : null;

  let graphAudioData = null;
  if (graphMode) {
    if (sessionAudio) {
      try {
        graphAudioData = JSON.parse(sessionAudio);
        wireGraphAnalysisSection(clusters, graphAudioData);
      } catch (e) {
        console.warn('graph analysis: bad session audio', e);
        wireGraphAnalysisEmpty('Session recording data could not be read. Process audio again from Cleanup.');
      }
    } else {
      wireGraphAnalysisEmpty('No processed recording in this browser session yet.');
    }
  }

  if (clusters)        buildClusterChart('cluster-chart', clusters, graphAudioData);
  else                 showNoData('cluster-chart');

  // Model Insights charts
  if (modelInsights) {
    buildFeatureImportanceChart('feature-importance-chart', modelInsights);
    wireFeatureImportanceModal(modelInsights);
    buildClassMetricsChart('class-metrics-chart', modelInsights);
  } else {
    showNoData('feature-importance-chart');
    showNoData('class-metrics-chart');
  }

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
