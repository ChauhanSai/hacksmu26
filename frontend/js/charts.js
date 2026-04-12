/*
 * All Plotly chart builders.
 * Each function accepts a target DOM id and a data object from /data/*.json
 */

// Institutional dark palette — cyan leads, risk colors for emphasis.
const PALETTE = ['#7dd3fc', '#4ade80', '#fbbf24', '#fb923c', '#ef4444', '#c084fc'];
const GRID    = 'rgba(255,255,255,0.06)';
const AXIS    = 'rgba(243,245,247,0.55)';
const FONT    = { family: 'Geist, Inter, sans-serif', size: 11, color: 'rgba(243,245,247,0.78)' };

const BASE_LAYOUT = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor:  'rgba(0,0,0,0)',
  font: FONT,
  margin: { l: 60, r: 20, t: 20, b: 60 },
  xaxis: { gridcolor: GRID, linecolor: GRID, zerolinecolor: GRID, tickcolor: GRID, tickfont: { color: AXIS, size: 10 } },
  yaxis: { gridcolor: GRID, linecolor: GRID, zerolinecolor: GRID, tickcolor: GRID, tickfont: { color: AXIS, size: 10 } },
  hoverlabel: {
    bgcolor: 'rgba(7,9,12,0.95)',
    bordercolor: 'rgba(125,211,252,0.35)',
    font: { family: 'Geist Mono, monospace', size: 11, color: '#7dd3fc' },
  },
};

const CONFIG = { displaylogo: false, responsive: true };

// Keep references so we can toggle explain-mode hover labels after render
const registry = new Map();

function registerChart(id, updater) {
  registry.set(id, updater);
}

document.addEventListener('explain-toggle', (e) => {
  registry.forEach((updater) => updater(e.detail.on));
});


// ═══════════════════════════════════════════════════════════════════════════
// 1. CLUSTER SCATTER (UMAP)
// ═══════════════════════════════════════════════════════════════════════════

function buildClusterChart(target, data) {
  const { points, clusters } = data;
  const traces = [];

  // ── Density heatmap background ────────────────────────────────────────────
  traces.push({
    type: 'histogram2dcontour',
    x: points.map(p => p.x),
    y: points.map(p => p.y),
    colorscale: [[0, 'rgba(0,0,0,0)'], [1, 'rgba(125,211,252,0.18)']],
    showscale: false,
    ncontours: 18,
    contours: { showlines: false },
    hoverinfo: 'skip',
    showlegend: false,
  });

  // ── Convex hull polygons ──────────────────────────────────────────────────
  clusters.forEach((c, i) => {
    if (!c.hull || c.hull.length < 3) return;
    const rgb = hexToRgb(PALETTE[i % PALETTE.length]);
    traces.push({
      type: 'scatter',
      mode: 'lines',
      x: c.hull.map(pt => pt[0]),
      y: c.hull.map(pt => pt[1]),
      fill: 'toself',
      fillcolor: `rgba(${rgb.r},${rgb.g},${rgb.b},0.06)`,
      line: { color: `rgba(${rgb.r},${rgb.g},${rgb.b},0.45)`, width: 1.2, dash: 'dot' },
      hoverinfo: 'skip',
      showlegend: false,
    });
  });

  // ── One scatter trace per cluster (for legend + color) ────────────────────
  const byCluster = new Map();
  points.forEach(p => {
    if (!byCluster.has(p.cluster)) byCluster.set(p.cluster, []);
    byCluster.get(p.cluster).push(p);
  });

  const detailedHover = p =>
    `<b>${p.filename}</b><br>` +
    `Cluster ${p.cluster} (${clusters[p.cluster]?.top_context || '?'})<br>` +
    `Context: ${p.context}<br>` +
    `Caller: ${p.elephant_id} (${p.age_sex})<br>` +
    `Sound: ${p.sound_type} · ${p.comm_mode}<br>` +
    `Country: ${p.country} · Session ${p.session_id}<br>` +
    (p.mean_f0 ? `F0: ${p.mean_f0.toFixed(1)} Hz · Dur: ${p.duration?.toFixed(2)}s` : '') +
    '<extra></extra>';

  const simpleHover = p =>
    `A ${p.context} call by a ${p.age_sex}<extra></extra>`;

  const scatterTraces = [];
  clusters.forEach((c, i) => {
    const pts = byCluster.get(c.id) || [];
    if (pts.length === 0) return;
    const color = PALETTE[i % PALETTE.length];
    const trace = {
      type: 'scattergl',
      mode: 'markers',
      name: c.label,
      x: pts.map(p => p.x),
      y: pts.map(p => p.y),
      marker: {
        color,
        size: 7,
        opacity: 0.85,
        line: { color: 'rgba(7,9,12,0.6)', width: 0.5 },
      },
      customdata: pts,
      hovertemplate: pts.map(detailedHover),
    };
    traces.push(trace);
    scatterTraces.push({ trace, pts });
  });

  // ── Cluster centroid labels ───────────────────────────────────────────────
  const annotations = clusters
    .filter(c => c.count > 0)
    .map(c => ({
      x: c.centroid[0],
      y: c.centroid[1],
      text: `<b>C${c.id}</b>`,
      showarrow: false,
      font: { size: 9, color: '#7dd3fc', family: 'Geist Mono, monospace' },
      bgcolor: 'rgba(7,9,12,0.78)',
      bordercolor: 'rgba(125,211,252,0.35)',
      borderwidth: 1,
      borderpad: 3,
    }));

  const layout = {
    ...BASE_LAYOUT,
    xaxis: { title: { text: 'UMAP 1', font: { color: AXIS } }, showgrid: false, zeroline: false, ticks: '', tickfont: { color: AXIS } },
    yaxis: { title: { text: 'UMAP 2', font: { color: AXIS } }, showgrid: false, zeroline: false, ticks: '', tickfont: { color: AXIS } },
    legend: {
      orientation: 'v',
      x: 1.02, y: 1,
      font: { size: 10, color: AXIS, family: 'Geist Mono, monospace' },
      bgcolor: 'rgba(0,0,0,0)',
      bordercolor: 'rgba(255,255,255,0.08)',
      borderwidth: 1,
    },
    annotations,
    margin: { l: 60, r: 190, t: 20, b: 60 },
  };

  Plotly.newPlot(target, traces, layout, CONFIG);

  // Register explain-mode updater (swap hover templates)
  registerChart(target, (on) => {
    const update = {};
    const indices = [];
    traces.forEach((t, i) => {
      if (t.mode === 'markers' && t.customdata) {
        indices.push(i);
      }
    });
    // Recompute templates for scatter traces
    const newTemplates = indices.map(i => {
      const t = traces[i];
      return t.customdata.map(on ? simpleHover : detailedHover);
    });
    Plotly.restyle(target, { hovertemplate: newTemplates }, indices);
  });
}


// ═══════════════════════════════════════════════════════════════════════════
// 2. PMI HEATMAP
// ═══════════════════════════════════════════════════════════════════════════

function buildPmiChart(target, data) {
  const trace = {
    type: 'heatmap',
    z: data.values,
    x: data.contexts,
    y: data.symbols,
    colorscale: [
      [0,    '#ef4444'],   // critical / avoided
      [0.5,  '#10151c'],   // neutral — dark panel
      [1,    '#7dd3fc'],   // positive association — cyan
    ],
    zmid: 0,
    hovertemplate: '<b>%{y}</b> × %{x}<br>PMI: %{z:.2f}<extra></extra>',
    colorbar: {
      title: { text: 'PMI', font: { color: AXIS } },
      thickness: 10, len: 0.8,
      tickfont: { color: AXIS, family: 'Geist Mono, monospace' },
      outlinewidth: 0,
    },
  };
  const layout = {
    ...BASE_LAYOUT,
    xaxis: { tickangle: -35, automargin: true, tickfont: { size: 9, color: AXIS }, gridcolor: GRID },
    yaxis: { automargin: true, tickfont: { size: 10, color: AXIS }, gridcolor: GRID },
    margin: { l: 60, r: 30, t: 10, b: 120 },
  };
  Plotly.newPlot(target, [trace], layout, CONFIG);

  registerChart(target, (on) => {
    Plotly.restyle(target, {
      hovertemplate: on
        ? 'This call type matches this behavior<extra></extra>'
        : '<b>%{y}</b> × %{x}<br>PMI: %{z:.2f}<extra></extra>',
    });
  });
}


// ═══════════════════════════════════════════════════════════════════════════
// 3. TRANSITION MATRIX
// ═══════════════════════════════════════════════════════════════════════════

function buildTransitionChart(target, data) {
  const trace = {
    type: 'heatmap',
    z: data.values,
    x: data.symbols,
    y: data.symbols,
    colorscale: [
      [0,   '#0b0f14'],
      [0.5, '#1e40af'],
      [1,   '#7dd3fc'],
    ],
    hovertemplate: '%{y} → %{x}<br>Prob: %{z:.2f}<extra></extra>',
    colorbar: {
      title: { text: 'P', font: { color: AXIS } },
      thickness: 10, len: 0.8,
      tickfont: { color: AXIS, family: 'Geist Mono, monospace' },
      outlinewidth: 0,
    },
  };
  const layout = {
    ...BASE_LAYOUT,
    xaxis: { title: { text: 'Next symbol', font: { color: AXIS } }, automargin: true, tickfont: { size: 9, color: AXIS }, gridcolor: GRID },
    yaxis: { title: { text: 'Current symbol', font: { color: AXIS } }, automargin: true, tickfont: { size: 9, color: AXIS }, gridcolor: GRID },
    margin: { l: 70, r: 30, t: 10, b: 60 },
  };
  Plotly.newPlot(target, [trace], layout, CONFIG);

  registerChart(target, (on) => {
    Plotly.restyle(target, {
      hovertemplate: on
        ? 'Chance this call follows another<extra></extra>'
        : '%{y} → %{x}<br>Prob: %{z:.2f}<extra></extra>',
    });
  });
}


// ═══════════════════════════════════════════════════════════════════════════
// 4. VOWEL SPACE (F1 / F2)
// ═══════════════════════════════════════════════════════════════════════════

function buildVowelChart(target, data) {
  const trace = {
    type: 'scattergl',
    mode: 'markers',
    x: data.f2,
    y: data.f1,
    marker: {
      color: data.clusters,
      colorscale: [
        [0,    '#7dd3fc'],
        [0.25, '#4ade80'],
        [0.5,  '#fbbf24'],
        [0.75, '#fb923c'],
        [1,    '#ef4444'],
      ],
      size: 6,
      opacity: 0.78,
      line: { color: 'rgba(7,9,12,0.6)', width: 0.3 },
      colorbar: {
        title: { text: 'cluster', font: { color: AXIS } },
        thickness: 8, len: 0.7,
        tickfont: { color: AXIS, family: 'Geist Mono, monospace' },
        outlinewidth: 0,
      },
    },
    text: data.contexts,
    hovertemplate: '<b>F1:</b> %{y:.0f} Hz<br><b>F2:</b> %{x:.0f} Hz<br>%{text}<extra></extra>',
  };
  const layout = {
    ...BASE_LAYOUT,
    xaxis: { title: { text: 'F2 (Hz)', font: { color: AXIS } }, autorange: 'reversed', showgrid: true, gridcolor: GRID, tickfont: { color: AXIS } },
    yaxis: { title: { text: 'F1 (Hz)', font: { color: AXIS } }, autorange: 'reversed', showgrid: true, gridcolor: GRID, tickfont: { color: AXIS } },
  };
  Plotly.newPlot(target, [trace], layout, CONFIG);

  registerChart(target, (on) => {
    Plotly.restyle(target, {
      hovertemplate: on
        ? 'A mouth-shape category like a vowel<extra></extra>'
        : '<b>F1:</b> %{y:.0f} Hz<br><b>F2:</b> %{x:.0f} Hz<br>%{text}<extra></extra>',
    });
  });
}


// ═══════════════════════════════════════════════════════════════════════════
// 5. CONTEXT DISTRIBUTION BARS
// ═══════════════════════════════════════════════════════════════════════════

function buildContextChart(target, data) {
  const colors = data.contexts.map((_, i) => PALETTE[i % PALETTE.length]);
  const trace = {
    type: 'bar',
    x: data.contexts,
    y: data.counts,
    marker: {
      color: colors,
      line: { color: 'rgba(255,255,255,0.14)', width: 0.5 },
    },
    hovertemplate: '<b>%{x}</b><br>%{y} calls<extra></extra>',
  };
  const layout = {
    ...BASE_LAYOUT,
    xaxis: { tickangle: -35, automargin: true, tickfont: { size: 9, color: AXIS }, gridcolor: GRID },
    yaxis: { title: { text: 'Calls', font: { color: AXIS } }, gridcolor: GRID, tickfont: { color: AXIS } },
    margin: { l: 60, r: 20, t: 10, b: 120 },
  };
  Plotly.newPlot(target, [trace], layout, CONFIG);

  registerChart(target, (on) => {
    Plotly.restyle(target, {
      hovertemplate: on
        ? 'Number of calls in this behavior<extra></extra>'
        : '<b>%{x}</b><br>%{y} calls<extra></extra>',
    });
  });
}


// ═══════════════════════════════════════════════════════════════════════════
// 6. CALLER IDENTIFIABILITY BAR
// ═══════════════════════════════════════════════════════════════════════════

function buildIdentifiabilityChart(target, data) {
  const colors = data.callers.map((_, i) => PALETTE[i % PALETTE.length]);
  const trace = {
    type: 'bar',
    orientation: 'h',
    x: data.scores,
    y: data.callers,
    marker: { color: colors },
    text: data.n_calls.map(n => `n=${n}`),
    textposition: 'outside',
    hovertemplate: '<b>%{y}</b><br>Identifiability: %{x:.2f}<extra></extra>',
  };
  const layout = {
    ...BASE_LAYOUT,
    xaxis: { title: 'Identifiability score', gridcolor: '#f5efdf' },
    yaxis: { automargin: true, autorange: 'reversed' },
    margin: { l: 80, r: 50, t: 10, b: 50 },
  };
  Plotly.newPlot(target, [trace], layout, CONFIG);

  registerChart(target, (on) => {
    Plotly.restyle(target, {
      hovertemplate: on
        ? 'How unique this elephant sounds<extra></extra>'
        : '<b>%{y}</b><br>Identifiability: %{x:.2f}<extra></extra>',
    });
  });
}


// ═══════════════════════════════════════════════════════════════════════════
// helpers
// ═══════════════════════════════════════════════════════════════════════════

function hexToRgb(hex) {
  const m = hex.replace('#', '').match(/.{2}/g);
  return { r: parseInt(m[0], 16), g: parseInt(m[1], 16), b: parseInt(m[2], 16) };
}
