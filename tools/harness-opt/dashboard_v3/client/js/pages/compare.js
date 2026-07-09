import { clear, h } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { card } from "../components/widgets.js";

function meanByTask(rows) {
  const acc = {};
  rows.forEach((r) => {
    (acc[r.task_id] = acc[r.task_id] || []).push(r.reward);
  });
  const out = {};
  for (const [t, rs] of Object.entries(acc)) out[t] = rs.reduce((a, b) => a + b, 0) / rs.length;
  return out;
}

export function ComparePage() {
  const wrap = h("div", { class: "page" });
  const others = store.runs.map((r) => r.run).filter((r) => r !== store.run);
  if (!others.length) {
    wrap.appendChild(h("div", { class: "empty" }, "Need at least two analyzed runs to compare."));
    return wrap;
  }

  const baselineDefault =
    store.summary.manifest.baseline_run && others.includes(store.summary.manifest.baseline_run)
      ? store.summary.manifest.baseline_run
      : others[0];

  const out = h("div", { class: "panel" });
  const sel = h(
    "select",
    { class: "select", onchange: (e) => run(e.target.value) },
    ...others.map((r) => h("option", { value: r, selected: r === baselineDefault }, r)),
  );
  wrap.appendChild(
    h("div", { class: "panel-head" }, h("h3", {}, `Candidate ${store.run} vs baseline:`), sel),
  );
  wrap.appendChild(out);

  async function run(baseline) {
    clear(out);
    out.appendChild(h("div", { class: "spinner" }, "Loading…"));
    try {
      const [candRows, baseRows] = await Promise.all([api.tasks(store.run), api.tasks(baseline)]);
      const cand = meanByTask(candRows);
      const base = meanByTask(baseRows);
      const tasks = Array.from(new Set([...Object.keys(cand), ...Object.keys(base)]));
      const rows = tasks
        .map((t) => {
          const a = base[t] ?? 0,
            b = cand[t] ?? 0;
          const pa = a >= 0.999,
            pb = b >= 0.999;
          const flip = pa && !pb ? "regressed" : pb && !pa ? "improved" : "same";
          return { task: t, base: a, cand: b, delta: b - a, flip };
        })
        .filter((r) => Math.abs(r.delta) > 1e-9)
        .sort((a, b) => a.delta - b.delta);

      const improved = rows.filter((r) => r.flip === "improved").length;
      const regressed = rows.filter((r) => r.flip === "regressed").length;
      const meanDelta = tasks.length
        ? tasks.reduce((s, t) => s + ((cand[t] ?? 0) - (base[t] ?? 0)), 0) / tasks.length
        : 0;

      clear(out);
      out.appendChild(
        h(
          "div",
          { class: "cards" },
          card(improved, "improved"),
          card(regressed, "regressed"),
          card((meanDelta >= 0 ? "+" : "") + meanDelta.toFixed(3), "mean Δ reward"),
        ),
      );
      if (!rows.length) {
        out.appendChild(h("div", { class: "muted" }, "No per-task reward changes."));
        return;
      }
      const color = { improved: "#16a34a", regressed: "#dc2626", same: "#9ca3af" };
      rows.forEach((r) => {
        const w = Math.abs(r.delta) * 100;
        out.appendChild(
          h(
            "div",
            { class: "cmprow" },
            h("span", { class: "cmptask mono" }, "task " + r.task),
            h(
              "span",
              { class: "cmpbarwrap" },
              h("div", { class: "cmpbar", style: { width: Math.max(w, 2) + "%", background: color[r.flip] } }),
            ),
            h("span", { class: "cmpdelta" }, (r.delta >= 0 ? "+" : "") + r.delta.toFixed(2)),
          ),
        );
      });
    } catch (e) {
      clear(out);
      out.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
    }
  }

  run(baselineDefault);
  return wrap;
}
