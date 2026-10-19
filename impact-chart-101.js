'use strict';

let analysis;
let selected;
let showAll = false;
let priority = 'balanced';
let chart;
let visibleRows = [];

const categoryNames = {
  performance: 'PERFORMANCE',
  security_privacy: 'SECURITY & PRIVACY',
  reliability: 'RELIABILITY',
  engineering_enablement: 'ENGINEERING ENABLEMENT',
  customer_value: 'CUSTOMER VALUE',
};
// Fixed order, validated categorical palette (colour follows the category, never the rank).
const categoryColors = {
  performance: '#2a78d6',
  security_privacy: '#eb6834',
  reliability: '#1baf7a',
  engineering_enablement: '#eda100',
  customer_value: '#e87ba4',
};
const legendNames = {
  performance: 'Performance',
  security_privacy: 'Security & privacy',
  reliability: 'Reliability',
  engineering_enablement: 'Eng. enablement',
  customer_value: 'Customer value',
};
const INK = '#202c39';
const MUTED = '#647078';
const SURFACE = '#fffefa';

const $ = id => document.getElementById(id);

function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function link(text, url, className) {
  const a = node('a', text, className);
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  return a;
}
function paragraph(parent, text, className) { parent.append(node('p', text, className)); }

function weights() { return priority === 'outcome' ? [2, 1] : priority === 'reach' ? [1, 2] : [1, 1]; }
function maxScore() { const [a, b] = weights(); return 3 * (4 * a + 3 * b); }
function points(i) { const [a, b] = weights(); return a * i.outcome_strength + b * i.reach; }
function formula(i) {
  const [a, b] = weights();
  const o = a === 2 ? `2×${i.outcome_strength}` : String(i.outcome_strength);
  const r = b === 2 ? `2×${i.reach}` : String(i.reach);
  return `outcome ${o} + reach ${r} = ${points(i)}`;
}
function withAlpha(hex, alpha) {
  return hex + Math.round(alpha * 255).toString(16).padStart(2, '0');
}
function truncate(text, n) { return text.length > n ? text.slice(0, n - 1) + '…' : text; }

function ranked(){
  const [a,b]=weights();
  const rows=analysis.engineers.map(e=>{
    const initiatives=[...(e.all_reviewed_initiatives||e.counted_initiatives)]
      .sort((x,y)=>(a*y.outcome_strength+b*y.reach)-(a*x.outcome_strength+b*x.reach)||(y.evidence_grade??1)-(x.evidence_grade??1)||y.reach-x.reach||x.initiative.localeCompare(y.initiative)).slice(0,3);
    return {...e,initiatives,displayScore:initiatives.reduce((s,i)=>s+a*i.outcome_strength+b*i.reach,0),
      evidenceTotal:initiatives.reduce((s,i)=>s+(i.evidence_grade??1),0),reachTotal:initiatives.reduce((s,i)=>s+i.reach,0)};
  }).sort((x,y)=>y.displayScore-x.displayScore||y.evidenceTotal-x.evidenceTotal||y.reachTotal-x.reachTotal||x.author.toLowerCase().localeCompare(y.author.toLowerCase()));
  let last,rank;rows.forEach((e,i)=>{if(e.displayScore!==last)rank=i+1;e.displayRank=rank;e.displayPosition=i+1;last=e.displayScore;});return rows;
}

/* ---------- Chart ---------- */

// Bars grow to fill the panel on tall screens; long lists scroll inside the panel.
function rowHeight(count) {
  const panel = $('chart-panel');
  if (window.innerWidth <= 850 || !panel.clientHeight) return 34;
  return Math.max(28, Math.min(46, Math.floor((panel.clientHeight - 62) / count)));
}

const barLabels = {
  id: 'barLabels',
  afterDatasetsDraw(c) {
    const { ctx } = c;
    ctx.save();
    ctx.textBaseline = 'middle';
    const ends = [];
    c.data.datasets.forEach((ds, d) => {
      const meta = c.getDatasetMeta(d);
      meta.data.forEach((bar, i) => {
        const value = ds.data[i];
        if (value == null) return;
        ends[i] = Math.max(ends[i] || 0, bar.x);
        const width = bar.x - bar.base;
        if (width < 18) return;
        const row = visibleRows[i];
        const category = row.initiatives[d].category;
        ctx.globalAlpha = row.author === selected ? 1 : 0.55;
        ctx.fillStyle = category === 'performance' ? '#ffffff' : INK;
        ctx.font = '600 11px Inter, Segoe UI, Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(String(value), (bar.x + bar.base) / 2, bar.y);
      });
    });
    ctx.globalAlpha = 1;
    ctx.textAlign = 'left';
    visibleRows.forEach((row, i) => {
      if (ends[i] == null) return;
      const y = c.getDatasetMeta(0).data[i].y;
      ctx.fillStyle = row.author === selected ? INK : MUTED;
      ctx.font = `${row.author === selected ? 700 : 600} 13px Inter, Segoe UI, Arial, sans-serif`;
      ctx.fillText(String(row.displayScore), ends[i] + 7, y);
    });
    // Top-5 cutoff marker when the full reviewed list is shown
    const inTop = Math.min(5, visibleRows.length);
    if (inTop && inTop < visibleRows.length) {
      const y = c.scales.y.getPixelForValue(inTop - 0.5);
      const { left, right } = c.chartArea;
      ctx.strokeStyle = MUTED;
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(left - 140, y);
      ctx.lineTo(right, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = MUTED;
      ctx.font = '600 9px Inter, Segoe UI, Arial, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText('FEATURED 5 CUTOFF', right, y - 6);
    }
    ctx.restore();
  },
};

function lastSegmentIndex(row) { return Math.min(row.initiatives.length, 3) - 1; }

function chartData() {
  const labels = visibleRows.map(r => `${String(r.displayPosition).padStart(2, '0')}   ${r.author}`);
  const datasets = [0, 1, 2].map(k => ({
    label: ['Strongest initiative', 'Second initiative', 'Third initiative'][k],
    data: visibleRows.map(r => (r.initiatives[k] ? points(r.initiatives[k]) : null)),
    backgroundColor: visibleRows.map(r => {
      const i = r.initiatives[k];
      if (!i) return 'transparent';
      const color = categoryColors[i.category] || MUTED;
      return r.author === selected ? color : withAlpha(color, 0.4);
    }),
    hoverBackgroundColor: visibleRows.map(r => {
      const i = r.initiatives[k];
      return i ? (categoryColors[i.category] || MUTED) : 'transparent';
    }),
    borderColor: SURFACE,
    borderWidth: { top: 0, bottom: 0, left: 0, right: 2 },
    borderSkipped: false,
    borderRadius: ctx => (ctx.dataIndex !== undefined && visibleRows[ctx.dataIndex] && lastSegmentIndex(visibleRows[ctx.dataIndex]) === k
      ? { topLeft: 0, bottomLeft: 0, topRight: 4, bottomRight: 4 } : 0),
    categoryPercentage: 0.72,
    barPercentage: 1,
  }));
  return { labels, datasets };
}

function selectByIndex(i) {
  if (i < 0 || i >= visibleRows.length) return;
  selected = visibleRows[i].author;
  render();
}

function buildChart() {
  const canvas = $('impact-chart');
  chart = new Chart(canvas, {
    type: 'bar',
    data: chartData(),
    plugins: [barLabels],
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 350 },
      layout: { padding: { right: 30, top: 4 } },
      interaction: { mode: 'y', intersect: false },
      scales: {
        x: {
          stacked: true,
          min: 0,
          max: maxScore(),
          ticks: { stepSize: 3, color: MUTED, font: { size: 10 } },
          grid: { color: '#ecebe4' },
          border: { display: false },
          title: { display: true, text: 'Impact points · sum of 3 strongest initiatives', color: MUTED, font: { size: 10 } },
        },
        y: {
          stacked: true,
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: ctx => (visibleRows[ctx.index] && visibleRows[ctx.index].author === selected ? INK : MUTED),
            font: ctx => ({ size: 12, weight: visibleRows[ctx.index] && visibleRows[ctx.index].author === selected ? '700' : '500' }),
          },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: INK,
          padding: 10,
          boxPadding: 4,
          titleFont: { size: 12, weight: '700' },
          bodyFont: { size: 11 },
          footerFont: { size: 10, weight: '500' },
          footerColor: '#c3c9cd',
          filter: item => item.raw != null,
          callbacks: {
            title: items => {
              const r = visibleRows[items[0].dataIndex];
              return `${r.author} · ${r.displayScore} / ${maxScore()} points`;
            },
            label: item => {
              const i = visibleRows[item.dataIndex].initiatives[item.datasetIndex];
              return ` ${truncate(i.initiative, 46)}`;
            },
            afterLabel: item => {
              const i = visibleRows[item.dataIndex].initiatives[item.datasetIndex];
              return `   ${legendNames[i.category] || i.category} · ${formula(i)}`;
            },
            labelColor: item => {
              const i = visibleRows[item.dataIndex].initiatives[item.datasetIndex];
              const color = categoryColors[i.category] || MUTED;
              return { borderColor: color, backgroundColor: color, borderRadius: 2 };
            },
            footer: () => 'Click to see the evidence →',
          },
        },
      },
      onHover: (event, elements, c) => {
        const inArea = event.y >= c.chartArea.top && event.y <= c.chartArea.bottom;
        c.canvas.style.cursor = inArea ? 'pointer' : 'default';
      },
      onClick: (event, elements, c) => {
        if (event.y < c.chartArea.top || event.y > c.chartArea.bottom) return;
        const value = c.scales.y.getValueForPixel(event.y);
        selectByIndex(Math.round(value));
      },
    },
  });
  canvas.addEventListener('keydown', event => {
    const current = visibleRows.findIndex(r => r.author === selected);
    if (event.key === 'ArrowDown') { event.preventDefault(); selectByIndex(Math.min(current + 1, visibleRows.length - 1)); }
    if (event.key === 'ArrowUp') { event.preventDefault(); selectByIndex(Math.max(current - 1, 0)); }
  });
}

function renderLegend() {
  const legend = $('chart-legend');
  if (legend.childElementCount) return;
  for (const [key, name] of Object.entries(legendNames)) {
    const item = node('span', undefined, 'legend-item');
    const swatch = node('span', undefined, 'swatch');
    swatch.style.background = categoryColors[key];
    item.append(swatch, document.createTextNode(name));
    legend.append(item);
  }
}

function renderChart() {
  $('chart-box').style.height = `${visibleRows.length * rowHeight(visibleRows.length) + 58}px`;
  if (!chart) { buildChart(); return; }
  const data = chartData();
  chart.data.labels = data.labels;
  chart.data.datasets.forEach((ds, k) => Object.assign(ds, data.datasets[k]));
  chart.options.scales.x.max = maxScore();
  chart.resize();
  chart.update();
}

/* ---------- Fallback list (used only if Chart.js fails to load) ---------- */

function renderList() {
  $('engineers').replaceChildren();
  for (const e of visibleRows) {
    const button = node('button', undefined, 'person' + (selected === e.author ? ' selected' : ''));
    button.type = 'button';
    button.setAttribute('aria-pressed', String(selected === e.author));
    button.append(node('span', String(e.displayPosition).padStart(2, '0'), 'rank'));
    const name = node('span');
    name.append(node('span', e.author, 'person-name'), node('span', `${e.reviewed_initiative_count} assessed initiatives`, 'person-sub'));
    const score = node('span', String(e.displayScore), 'score');
    score.append(node('small', ` / ${maxScore()}`));
    button.append(name, score);
    button.addEventListener('click', () => { selected = e.author; render(); });
    $('engineers').append(button);
  }
}

/* ---------- Page ---------- */

function render() {
  const rows = ranked();
  visibleRows = showAll ? rows : rows.slice(0, 5);
  if (!visibleRows.some(e => e.author === selected)) selected = visibleRows[0].author;
  if (window.Chart) {
    renderLegend();
    renderChart();
    const r = visibleRows.find(e => e.author === selected);
    $('impact-chart').setAttribute('aria-label',
      `Stacked bar chart of impact points for ${visibleRows.length} engineers. Selected: ${r.author}, rank ${r.displayRank}, ${r.displayScore} of ${maxScore()} points. Use the up and down arrow keys to change the selected engineer.`);
  } else {
    $('chart-panel').hidden = true;
    $('engineers').hidden = false;
    renderList();
  }
  $('show-all').textContent = showAll ? 'Show top 5 only' : `Show all ${rows.length} reviewed`;
  const cutoff = rows[4]?.displayScore;
  const alternatives = rows.slice(5).filter(e => e.displayScore === cutoff).length;
  $('tie-note').textContent = `Five featured engineers; equal scores remain tied. Selection prefers inspected evidence support, then reach.${alternatives ? ` ${alternatives} others share the cutoff score; see all reviewed.` : ''}`;
  renderDetail(visibleRows.find(e => e.author === selected));
}

function meter(label, value, max) {
  const wrap = node('span', undefined, 'meter');
  wrap.append(node('span', label, 'meter-label'));
  for (let i = 1; i <= max; i++) wrap.append(node('span', undefined, 'pip' + (i <= value ? ' on' : '')));
  wrap.setAttribute('aria-label', `${label} ${value} of ${max}`);
  return wrap;
}

function renderDetail(e) {
  const target = $('detail');
  target.replaceChildren();
  const header = node('div', undefined, 'detail-header');
  const identity = node('div');
  identity.append(node('p', `FEATURED #${e.displayPosition} · CONTRIBUTION EVIDENCE`, 'eyebrow'), node('h2', e.author),
    link('View GitHub profile ↗', `https://github.com/${encodeURIComponent(e.author)}`, 'profile'));
  const total = node('div');
  const number = node('div', String(e.displayScore), 'total');
  number.append(node('small', ` / ${maxScore()}`));
  total.append(number, node('span', 'IMPACT POINTS', 'score-label'));
  header.append(identity, total);
  target.append(header);
  if (e.summary) paragraph(target, e.summary, 'detail-intro');
  paragraph(target, 'Their strongest reviewed initiatives. Each is scored on outcome (how much it improved things, 0–4) plus reach (how much of PostHog it touches, 0–3).', 'detail-intro');
  for (const i of e.initiatives) {
    const article = node('article', undefined, 'initiative');
    article.style.borderLeftColor = categoryColors[i.category] || MUTED;
    const top = node('div', undefined, 'initiative-top');
    const pill = node('span', undefined, 'pill');
    const swatch = node('span', undefined, 'swatch');
    swatch.style.background = categoryColors[i.category] || MUTED;
    pill.append(swatch, document.createTextNode(categoryNames[i.category] || i.category));
    const scoreLine = node('span', undefined, 'mini-score');
    scoreLine.append(meter('Outcome', i.outcome_strength, 4), meter('Reach', i.reach, 3), node('strong', `${points(i)} pts`, 'pts'));
    top.append(pill, scoreLine);
    article.append(top, node('h3', i.initiative));
    paragraph(article, i.reason);
    paragraph(article, i.evidence, 'evidence');
    if (i.reported_result) paragraph(article, i.reported_result + ' Not independently reproduced.', 'reported');
    const links = node('div', undefined, 'links');
    for (const source of i.sources) {
      const a = link(`#${source.number} ↗`, source.url);
      a.title = source.title;
      links.append(a);
    }
    article.append(links);
    const details = node('details');
    details.append(node('summary', 'Verification & limitations'));
    if (i.evidence_label) paragraph(details, `Evidence: ${i.evidence_label}. Delivery: ${i.delivery_status.replaceAll('_', ' ')}.`);
    paragraph(details, i.verification);
    paragraph(details, i.limitations);
    article.append(details);
    target.append(article);
  }
  paragraph(target, 'Analyst-assessed public evidence. A one-point difference is not proof of better overall performance.', 'detail-bottom');
}

function methodology() {
  const t = $('method-content');
  t.replaceChildren();
  const c = analysis.coverage;
  paragraph(t, analysis.methodology.formula);
  const definitions = [
    ['Reading the chart', 'Each bar is one engineer. Each coloured segment is one of their three strongest reviewed initiatives, and its length is that initiative\'s points (outcome + reach). Colour shows the type of work. The number at the end of the bar is the total. Click a bar, or use the arrow keys, to see the evidence.'],
    ['Outcome strength · 0–4', '0 unknown; 1 small/localized; 2 meaningful improvement; 3 substantial obstacle or serious failure addressed; 4 exceptional outcome with unusually strong support.'],
    ['Supported reach · 0–3', '0 unknown; 1 narrow workflow; 2 product area or multiple workflows; 3 shared platform or documented broad population. Potential scope is not measured adoption.'],
    ['Collection versus review', `${c.unique_merged_prs.toLocaleString()} merged PRs collected across ${c.days} complete UTC days. ${c.human_authored_prs.toLocaleString()} PRs have identified human authors. ${c.reviewed_prs} PRs, grouped into ${c.reviewed_initiatives} initiatives across ${c.reviewed_authors} of ${c.human_authors} human authors, were selectively assessed using descriptions and relevant implementation/regression excerpts. All 193 human authors were screened. This revised subset retains the original 46 PRs and adds 11 previously assessed PRs from the same 25 authors. Unreviewed work is not zero impact.`],
    ['Attribution and grouping', 'Related PRs count as one initiative when they support a common outcome. Credit follows the human author, not the merge bot. PR counts, lines changed and description length earn no points.'],
    ['Evidence confidence', analysis.methodology.evidence + ' Author-reported benchmarks remain labeled. Merged does not necessarily mean deployed or adopted.'],
    ['Ties and priorities', analysis.methodology.ties + ' Exactly five engineers are featured. Numbered chart rows show selection order, not unique score ranks. Other cutoff ties remain accessible through Show all reviewed. The priority selector changes the weights (2× outcome or 2× reach), not the underlying assessments.'],
    ['What is missing', 'Private work, mentoring, planning, code reviews and shared contributions are not fully captured. This is a ranking of reviewed public work, not a comprehensive employee evaluation.'],
  ];
  for (const [title, text] of definitions) { t.append(node('h3', title)); paragraph(t, text); }
  const sources = node('p');
  sources.append(link('Source repository ↗', 'https://github.com/PostHog/posthog'), document.createTextNode(' · '), link('Download assessment data', 'dashboard_data.json'));
  t.append(sources);
}

async function start() {
  try {
    const response = await fetch('impact-data-57.json');
    if (!response.ok) throw new Error(`Data request failed (${response.status})`);
    analysis = await response.json();
    if (!Array.isArray(analysis.engineers) || !analysis.engineers.length) throw new Error('Analysis contains no reviewed engineers.');
    const c = analysis.coverage;
    $('stats').replaceChildren();
    for (const [value, label] of [
      ['20 JUL — 17 OCT 2026', `${c.days} complete days · UTC`],
      [c.unique_merged_prs.toLocaleString(), 'Merged PRs collected'],
      [`${c.reviewed_authors} / ${c.human_authors}`, `${c.screened_human_authors} screened · engineers reviewed`],
      [`${c.reviewed_prs} PRs → ${c.reviewed_initiatives} initiatives`, '46 original + 11 added · no volume points'],
    ]) {
      const stat = node('div', undefined, 'stat');
      stat.append(node('strong', value), node('span', label));
      $('stats').append(stat);
    }
    selected = analysis.engineers[0].author;
    methodology();
    render();
  } catch (error) {
    $('error').hidden = false;
    $('error').textContent = `The analysis could not be loaded. Please refresh the page. (${error.message})`;
  }
}

$('priority').addEventListener('change', event => { priority = event.target.value; render(); });
$('show-all').addEventListener('click', () => { showAll = !showAll; render(); });
$('method').addEventListener('click', () => { if (analysis) $('method-dialog').showModal(); });
$('close-dialog').addEventListener('click', () => $('method-dialog').close());
$('download').addEventListener('click', () => {
  if (!analysis) return;
  const blob = new Blob([JSON.stringify(analysis, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = node('a');
  a.href = url;
  a.download = 'posthog-impact-analysis.json';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
let resizeTimer;
window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (analysis && chart) renderChart(); }, 150); });
start();
