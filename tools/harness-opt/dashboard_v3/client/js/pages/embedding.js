import { clear, h } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { navigate } from "../router.js";
import { ftypeColor } from "../components/widgets.js";

export function EmbeddingPage() {
  const wrap = h("div", { class: "page" });
  wrap.appendChild(
    h(
      "div",
      { class: "panel-head" },
      h("h3", {}, "Cluster embedding space"),
      h("span", { class: "muted tiny" }, "constructed from signal TF-IDF · PCA-2D · diagnostic, not the live partition function"),
    ),
  );
  const body = h("div", { class: "cmp-sections" });
  wrap.appendChild(body);
  load();
  return wrap;

  async function load() {
    clear(body);
    body.appendChild(h("div", { class: "spinner" }, "Computing embedding…"));
    try {
      const e = await api.embedding(store.run);
      clear(body);
      if (!e.clusters || e.clusters.length < 2) {
        body.appendChild(h("div", { class: "empty" }, "Need at least 2 failure clusters to visualize an embedding."));
        return;
      }
      body.appendChild(h("div", { class: "embed-cols" }, centroidPanel(e), scatterPanel(e)));
      body.appendChild(heatPanel(e));
    } catch (err) {
      clear(body);
      body.appendChild(h("div", { class: "error" }, "Failed: " + err.message));
    }
  }
}

const FONT = { family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', size: 11, color: "#1f2430" };

function plotLayout(showLegend) {
  return {
    margin: { l: 46, r: 14, t: 10, b: 42 },
    xaxis: { title: "PC1", zeroline: true, zerolinecolor: "#e5e8ee", gridcolor: "#f1f3f7" },
    yaxis: { title: "PC2", zeroline: true, zerolinecolor: "#e5e8ee", gridcolor: "#f1f3f7", scaleanchor: "x", scaleratio: 1 },
    showlegend: !!showLegend,
    legend: { orientation: "h", y: -0.16, font: { size: 10 } },
    hovermode: "closest",
    font: FONT,
    paper_bgcolor: "#fff",
    plot_bgcolor: "#fbfcfe",
  };
}

function renderPlot(div, data, layout, onClick) {
  requestAnimationFrame(() => {
    if (!window.Plotly) {
      div.appendChild(h("div", { class: "error" }, "Plotly failed to load (check /vendor/plotly.min.js)."));
      return;
    }
    window.Plotly.newPlot(div, data, layout, { responsive: true, displayModeBar: false }).then(() => {
      if (onClick) div.on("plotly_click", (ev) => ev.points && ev.points[0] && onClick(ev));
    });
  });
}

function centroidPanel(e) {
  const div = h("div", { class: "plot" });
  const maxCount = Math.max(...e.clusters.map((c) => c.count));
  const trace = {
    type: "scatter",
    mode: "markers+text",
    x: e.clusters.map((c) => c.x),
    y: e.clusters.map((c) => c.y),
    text: e.clusters.map((c) => c.id.replace("c_", "")),
    textposition: "middle center",
    textfont: { color: "#fff", size: 10 },
    marker: {
      size: e.clusters.map((c) => 12 + (Math.sqrt(c.count) / Math.sqrt(maxCount)) * 40),
      color: e.clusters.map((c) => ftypeColor(c.failure_type)),
      opacity: 0.82,
      line: { color: "#fff", width: 1 },
    },
    customdata: e.clusters.map((c) => c.id),
    hovertext: e.clusters.map((c) => `${c.id} · n=${c.count} · ${c.failure_type}<br>${c.gloss}`),
    hoverinfo: "text",
  };
  renderPlot(div, [trace], plotLayout(false), (ev) => navigate("/clusters", { c: ev.points[0].customdata }));
  return h(
    "div",
    { class: "panel" },
    h("h3", {}, "Centroid map"),
    h("div", { class: "muted tiny plot-cap" }, "each bubble = a cluster (size = #sims); nearby bubbles ≈ similar signatures. Click to open."),
    div,
  );
}

function scatterPanel(e) {
  const div = h("div", { class: "plot" });
  const byType = {};
  (e.points || []).forEach((p) => (byType[p.failure_type] = byType[p.failure_type] || []).push(p));
  const traces = Object.entries(byType).map(([t, pts]) => ({
    type: "scatter",
    mode: "markers",
    name: t,
    x: pts.map((p) => p.x),
    y: pts.map((p) => p.y),
    marker: { color: ftypeColor(t), size: 8, opacity: 0.68, line: { color: "#fff", width: 0.5 } },
    customdata: pts.map((p) => p.simulation_id),
    hovertext: pts.map((p) => `task ${p.task_id} · t${p.trial}<br>${p.cluster_id} · ${t}`),
    hoverinfo: "text",
  }));
  renderPlot(div, traces, plotLayout(true), (ev) => navigate("/traces", { a: ev.points[0].customdata }));
  return h(
    "div",
    { class: "panel" },
    h("h3", {}, "Sim scatter"),
    h("div", { class: "muted tiny plot-cap" }, "each point = a failing sim, colored by failure mode (shares the PC space). Click to open the trace."),
    div,
  );
}

function heatPanel(e) {
  const n = e.labels.length;
  const div = h("div", { class: "plot heat-plot" });
  const trace = {
    type: "heatmap",
    z: e.similarity,
    x: e.labels,
    y: e.labels,
    zmin: 0,
    zmax: 1,
    xgap: 1,
    ygap: 1,
    colorscale: [[0, "#f3f6ff"], [0.5, "#9db2fb"], [1, "#3b5bfd"]],
    colorbar: { thickness: 10, len: 0.85, outlinewidth: 0, tickfont: { size: 10 }, title: { text: "cos", side: "right", font: { size: 10 } } },
    hovertemplate: "%{y} ↔ %{x}<br>cosine %{z:.2f}<extra></extra>",
  };
  // show every tick only when there's room; otherwise let Plotly thin them
  const tick = { tickfont: { size: 9 }, automargin: true, showgrid: false, ...(n <= 30 ? { dtick: 1 } : {}) };
  const layout = {
    margin: { l: 58, r: 10, t: 8, b: 58 },
    font: FONT,
    paper_bgcolor: "#fff",
    plot_bgcolor: "#fff",
    xaxis: { ...tick, side: "bottom", constrain: "domain" },
    yaxis: { ...tick, autorange: "reversed", scaleanchor: "x", scaleratio: 1, constrain: "domain" },
  };
  renderPlot(div, [trace], layout, null);
  return h(
    "div",
    { class: "panel" },
    h("h3", {}, "Cluster similarity (centroid cosine)"),
    h("div", { class: "muted tiny plot-cap" }, "brighter cells = more similar centroids; bright off-diagonal pairs are near-duplicate clusters (merge candidates)."),
    div,
  );
}
