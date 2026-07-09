import { clear, h } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { navigate } from "../router.js";
import { ftype, ftypeColor } from "../components/widgets.js";

const PASS = 0.999;

function perTask(sims) {
  const m = {};
  for (const x of Object.values(sims)) {
    const t = (m[x.task_id] = m[x.task_id] || { rewards: [], fails: [] });
    t.rewards.push(x.reward);
    if (x.reward < PASS) t.fails.push(x.failure_type);
  }
  const out = {};
  for (const [t, v] of Object.entries(m)) {
    const mean = v.rewards.reduce((a, b) => a + b, 0) / v.rewards.length;
    out[t] = { mean, pass: mean >= PASS, fails: v.fails };
  }
  return out;
}

function ftypeCounts(sims) {
  const c = {};
  for (const x of Object.values(sims)) c[x.failure_type] = (c[x.failure_type] || 0) + 1;
  return c;
}

function totals(sims) {
  let cost = 0, steps = 0, n = 0, pass = 0;
  for (const x of Object.values(sims)) {
    cost += x.agent_cost || 0;
    steps += x.num_steps || 0;
    n += 1;
    if (x.reward >= PASS) pass += 1;
  }
  return { cost, meanSteps: n ? steps / n : 0, n, passRate: n ? pass / n : 0 };
}

function candFailSim(candSims, taskId) {
  for (const [sid, x] of Object.entries(candSims)) {
    if (x.task_id === taskId && x.reward < PASS) return sid;
  }
  return null;
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

  const sel = h(
    "select",
    { class: "select", onchange: (e) => render(e.target.value) },
    ...others.map((r) => h("option", { value: r, selected: r === baselineDefault }, r)),
  );
  wrap.appendChild(
    h(
      "div",
      { class: "panel-head" },
      h("h3", {}, ["Candidate: ", h("b", {}, store.run)]),
      h(
        "div",
        { class: "baseline-pick" },
        h("label", {}, "baseline run:"),
        sel,
      ),
    ),
  );
  const out = h("div", { class: "cmp-sections" });
  wrap.appendChild(out);

  async function render(baseline) {
    clear(out);
    out.appendChild(h("div", { class: "spinner" }, "Loading…"));
    try {
      const base = await api.summary(baseline);
      const cand = store.summary;
      clear(out);
      out.appendChild(headline(base, cand, baseline));
      out.appendChild(flow(base, cand));
      out.appendChild(modeShift(base, cand));
      out.appendChild(regressions(base, cand));
    } catch (e) {
      clear(out);
      out.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
    }
  }

  // ---- 1. headline metric table ----
  function headline(base, cand, baseName) {
    const tb = totals(base.sims), tc = totals(cand.sims);
    const row = (label, b, c, delta) =>
      h("tr", {}, h("td", { class: "muted" }, label), h("td", {}, b), h("td", {}, c), h("td", {}, delta || ""));
    const dpp = ((tc.passRate - tb.passRate) * 100);
    const deltaEl = h("span", { class: dpp >= 0 ? "up" : "down" }, `${dpp >= 0 ? "▲" : "▼"} ${Math.abs(dpp).toFixed(1)} pp`);
    const tbl = h(
      "table",
      { class: "tbl cmp-headline" },
      h("tr", {}, h("th", {}, "metric"), h("th", {}, baseName), h("th", {}, store.run + " (candidate)"), h("th", {}, "Δ")),
      row("agent LLM", base.manifest.agent_llm || "—", cand.manifest.agent_llm || "—"),
      row("pass rate", (tb.passRate * 100).toFixed(1) + "%", (tc.passRate * 100).toFixed(1) + "%", deltaEl),
      row("failing sims", tb.n - Math.round(tb.passRate * tb.n), tc.n - Math.round(tc.passRate * tc.n)),
      row("total agent cost", "$" + tb.cost.toFixed(2), "$" + tc.cost.toFixed(2), `$${(tc.cost - tb.cost >= 0 ? "+" : "") + (tc.cost - tb.cost).toFixed(2)}`),
      row("avg steps / sim", tb.meanSteps.toFixed(1), tc.meanSteps.toFixed(1)),
    );
    return h("div", { class: "panel" }, h("h3", {}, "Headline"), tbl);
  }

  // ---- 2. task outcome flow (2x2) ----
  function flow(base, cand) {
    const b = perTask(base.sims), c = perTask(cand.sims);
    const tasks = new Set([...Object.keys(b), ...Object.keys(c)]);
    const buckets = { improved: [], regressed: [], stillFail: [], stillPass: [] };
    for (const t of tasks) {
      const bp = b[t] && b[t].pass, cp = c[t] && c[t].pass;
      if (bp && cp) buckets.stillPass.push(t);
      else if (!bp && cp) buckets.improved.push(t);
      else if (bp && !cp) buckets.regressed.push(t);
      else buckets.stillFail.push(t);
    }
    const chip = (label, arr, cls) =>
      h("div", { class: "flowchip " + cls }, h("div", { class: "flow-n" }, arr.length), h("div", { class: "flow-l" }, label));
    return h(
      "div",
      { class: "panel" },
      h("h3", {}, `Task outcome flow (${tasks.size} tasks · "pass" = all trials passed)`),
      h(
        "div",
        { class: "flowgrid" },
        chip("regressed (was pass → now fail)", buckets.regressed, "bad"),
        chip("improved (was fail → now pass)", buckets.improved, "good"),
        chip("still failing (both)", buckets.stillFail, "warn"),
        chip("still passing (both)", buckets.stillPass, "neutral"),
      ),
    );
  }

  // ---- 3. failure-mode shift ----
  function modeShift(base, cand) {
    const cb = ftypeCounts(base.sims), cc = ftypeCounts(cand.sims);
    const types = Array.from(new Set([...Object.keys(cb), ...Object.keys(cc)]))
      .filter((t) => t !== "pass")
      .sort((a, b2) => (cc[b2] || 0) + (cb[b2] || 0) - ((cc[a] || 0) + (cb[a] || 0)));
    const max = Math.max(1, ...types.map((t) => Math.max(cb[t] || 0, cc[t] || 0)));
    const rows = types.map((t) => {
      const bv = cb[t] || 0, cv = cc[t] || 0, d = cv - bv;
      const barB = h("div", { class: "ms-bar" }, h("div", { class: "ms-fill base", style: { width: (bv / max) * 100 + "%", background: ftypeColor(t) } }), h("span", { class: "ms-num" }, bv));
      const barC = h("div", { class: "ms-bar" }, h("div", { class: "ms-fill", style: { width: (cv / max) * 100 + "%", background: ftypeColor(t) } }), h("span", { class: "ms-num" }, cv));
      return h(
        "div",
        { class: "ms-row" },
        h("div", { class: "ms-label" }, ftype(t)),
        h("div", { class: "ms-bars" }, h("div", { class: "ms-side" }, h("span", { class: "ms-tag" }, "base"), barB), h("div", { class: "ms-side" }, h("span", { class: "ms-tag" }, "cand"), barC)),
        h("div", { class: "ms-delta " + (d > 0 ? "down" : d < 0 ? "up" : "") }, d === 0 ? "—" : (d > 0 ? "+" : "") + d),
      );
    });
    return h(
      "div",
      { class: "panel" },
      h("h3", {}, "Failure-mode shift (sims per mode · candidate − baseline)"),
      rows.length ? h("div", { class: "ms" }, ...rows) : h("div", { class: "muted" }, "No failures in either run."),
    );
  }

  // ---- 4. actionable regressions ----
  function regressions(base, cand) {
    const b = perTask(base.sims), c = perTask(cand.sims);
    const regs = Object.keys(c)
      .filter((t) => b[t] && b[t].pass && !c[t].pass)
      .sort((x, y) => (Number(x) || 0) - (Number(y) || 0));
    const panel = h("div", { class: "panel" }, h("h3", {}, `Regressions — was passing, now failing (${regs.length})`));
    if (!regs.length) {
      panel.appendChild(h("div", { class: "muted" }, "No regressions. 🎉"));
      return panel;
    }
    const tbl = h("table", { class: "tbl" }, h("tr", {}, h("th", {}, "task"), h("th", {}, "now fails as"), h("th", {}, "")));
    regs.forEach((t) => {
      const modes = Array.from(new Set(c[t].fails));
      const sid = candFailSim(cand.sims, t);
      tbl.appendChild(
        h(
          "tr",
          {},
          h("td", { class: "mono" }, "task " + t),
          h("td", {}, ...modes.map((mm) => ftype(mm))),
          h("td", {}, sid ? h("button", { class: "btn small", onClick: () => navigate("/traces", { a: sid }) }, "open trace →") : null),
        ),
      );
    });
    panel.appendChild(tbl);
    return panel;
  }

  render(baselineDefault);
  return wrap;
}
