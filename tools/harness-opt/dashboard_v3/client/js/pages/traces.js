import { clear, h } from "../dom.js";
import { getSim } from "../api.js";
import { store } from "../store.js";
import { parseHash } from "../router.js";
import { badge, ftype, spinner } from "../components/widgets.js";
import { Waterfall } from "../components/waterfall.js";
import { DiffView } from "../components/diff.js";

const MAX_SEL = 2; // comparison is pairwise (diff needs exactly two)

export function TracesPage() {
  const s = store.summary;
  const { params } = parseHash();
  const sel = [params.get("a"), params.get("b")].filter(Boolean).slice(0, MAX_SEL);
  const state = { sel, diff: params.get("diff") === "1" && sel.length === 2, hideEqual: false, showReason: false };
  const openClusters = new Set();
  let filter = "";

  const wrap = h("div", { class: "page traces" });
  const left = h("div", { class: "panel trace-picker" });
  const main = h("div", { class: "trace-main" });
  wrap.appendChild(h("div", { class: "grid-tr" }, left, main));

  // ---------- selection ----------
  function add(sid) {
    if (state.sel.includes(sid) || state.sel.length >= MAX_SEL) return;
    state.sel.push(sid);
    renderMain();
    buildLeft();
  }
  function remove(sid) {
    state.sel = state.sel.filter((x) => x !== sid);
    if (state.sel.length !== 2) state.diff = false;
    renderMain();
    buildLeft();
  }
  function clearAll() {
    state.sel = [];
    state.diff = false;
    renderMain();
    buildLeft();
  }
  function loadFlaky(f) {
    state.sel = [f.pass_sim, f.fail_sim];
    state.diff = true;
    renderMain();
    buildLeft();
  }

  // ---------- left picker ----------
  function buildLeft() {
    clear(left);
    left.appendChild(
      h("input", {
        class: "search",
        placeholder: "filter tasks / clusters / signature…",
        value: filter,
        oninput: (e) => {
          filter = e.target.value;
          buildLeft();
          left.querySelector(".search").focus();
        },
      }),
    );
    const f = filter.toLowerCase();

    if ((s.flaky || []).length) {
      left.appendChild(h("div", { class: "sec-title" }, `⚡ Flaky — pass vs fail (${s.flaky.length})`));
      s.flaky.forEach((fl) => {
        if (f && !String(fl.task_id).toLowerCase().includes(f)) return;
        left.appendChild(
          h(
            "div",
            { class: "flaky", onClick: () => loadFlaky(fl) },
            h("span", { class: "lbl" }, ["task ", h("b", {}, String(fl.task_id)), ` · ${fl.n_trials} trials`]),
            h("span", { class: "go" }, "compare →"),
          ),
        );
      });
    }

    left.appendChild(h("div", { class: "sec-title" }, `Clusters (${s.clusters.length})`));
    const full = state.sel.length >= MAX_SEL;
    s.clusters.forEach((c) => {
      const hay = (c.id + " " + c.failure_type + " " + c.signature + " " +
        c.sims.map((x) => s.sims[x] && s.sims[x].task_id).join(" ")).toLowerCase();
      if (f && !hay.includes(f)) return;
      const isOpen = openClusters.has(c.id);
      const head = h(
        "div",
        {
          class: "clu-head",
          onClick: () => {
            isOpen ? openClusters.delete(c.id) : openClusters.add(c.id);
            buildLeft();
          },
        },
        h("span", { class: "caret" }, isOpen ? "▾" : "▸"),
        ftype(c.failure_type),
        h("span", { class: "cl-id" }, c.id),
        h("span", { class: "cl-count" }, c.count),
      );
      const box = h("div", { class: "clu-box" }, head);
      if (isOpen) {
        c.sims.forEach((sid) => {
          const m = s.sims[sid];
          if (!m) return;
          const inSel = state.sel.includes(sid);
          box.appendChild(
            h(
              "div",
              { class: "member" + (inSel ? " sel" : "") },
              h("span", { class: "lbl" }, `task ${m.task_id} · t${m.trial} · r=${m.reward.toFixed(1)}`),
              h(
                "span",
                {
                  class: "addbtn" + (inSel ? " on" : ""),
                  title: inSel ? "in view" : full ? "view is full (max 2)" : "add to comparison",
                  onClick: () => (inSel ? remove(sid) : add(sid)),
                },
                inSel ? "✓" : "+",
              ),
            ),
          );
        });
      }
      left.appendChild(box);
    });
  }

  // ---------- main ----------
  function chip(sid) {
    const m = s.sims[sid] || {};
    return h(
      "div",
      { class: "chip" },
      h("span", { class: "mono" }, (sid || "").slice(0, 8)),
      ` · t${m.trial} `,
      ftype(m.failure_type),
      ` r=${(m.reward ?? 0).toFixed(2)}`,
      h("span", { class: "chip-x", title: "remove from view", onClick: () => remove(sid) }, "✕"),
    );
  }

  function controls() {
    const two = state.sel.length === 2;
    const btn = (label, on, active, disabled) =>
      h("button", { class: "btn" + (active ? " active" : ""), disabled, onClick: on }, label);
    return h(
      "div",
      { class: "controls" },
      ...state.sel.map(chip),
      btn("Diff", () => { state.diff = !state.diff; renderMain(); }, state.diff, !two),
      btn("Hide equal", () => { state.hideEqual = !state.hideEqual; renderMain(); }, state.hideEqual, !(two && state.diff)),
      btn("Failure reason", () => { state.showReason = !state.showReason; renderMain(); }, state.showReason, !state.sel.length),
      btn("Clear all", clearAll, false, !state.sel.length),
    );
  }

  function reasonBlock(sim) {
    const fr = sim.failure_reason;
    if (!fr) return null;
    const rows = [
      h("div", { class: "rr-line" }, h("b", {}, "reward "), fr.reward.toFixed(2), " · basis ", (fr.reward_basis || []).join(" + ")),
    ];
    const bd = Object.entries(fr.reward_breakdown || {}).map(([k, v]) => `${k}=${v}`).join("   ");
    if (bd) rows.push(h("div", { class: "rr-line mono tiny" }, bd));
    if (fr.termination_reason && fr.termination_reason !== "user_stop")
      rows.push(h("div", { class: "rr-line" }, h("b", {}, "termination "), fr.termination_reason));
    if (sim.db_diff_signature)
      rows.push(h("div", { class: "rr-line" }, h("b", {}, "DB diff "), h("span", { class: "mono breakall" }, sim.db_diff_signature)));
    (fr.nl_failures || []).forEach((n) =>
      rows.push(
        h(
          "div",
          { class: "rr-nl" },
          h("div", { class: "rr-assert" }, "✗ " + n.assertion),
          n.justification ? h("div", { class: "rr-just" }, n.justification) : null,
        ),
      ),
    );
    (fr.communicate_failures || []).forEach((n) =>
      rows.push(
        h(
          "div",
          { class: "rr-nl" },
          h("div", { class: "rr-assert" }, "✗ communicate: " + n.info),
          n.justification ? h("div", { class: "rr-just" }, n.justification) : null,
        ),
      ),
    );
    if (rows.length <= 1 && !sim.db_diff_signature)
      rows.push(h("div", { class: "muted small" }, "No structured failure reason (passed, or reason not recorded)."));
    return h("div", { class: "reason" }, h("div", { class: "reason-title" }, "Golden failure reason"), ...rows);
  }

  function tracePanel(sim) {
    const cap = h(
      "div",
      { class: "wfcap" },
      h("span", {}, [
        h("span", { class: "mono" }, sim.simulation_id.slice(0, 8)),
        ` · task ${sim.task_id} · t${sim.trial} · `,
        ftype(sim.failure_type),
        ` · r=${sim.reward.toFixed(2)}`,
      ]),
      h("span", {}, `${(sim.total_dur || 0).toFixed(2)}s · ${sim.steps.length} steps · $${(sim.agent_cost || 0).toFixed(4)}`),
    );
    return h(
      "div",
      { class: "panel tracepanel" },
      cap,
      state.showReason ? reasonBlock(sim) : null,
      h("div", { class: "wfscroll" }, Waterfall(sim)),
    );
  }

  async function renderMain() {
    clear(main);
    main.appendChild(controls());
    if (!state.sel.length) {
      main.appendChild(h("div", { class: "empty" }, "Add a trace with + (or load a flaky pass↔fail pair) on the left."));
      return;
    }
    const body = h("div", { class: "trace-body" }, spinner("Loading trace…"));
    main.appendChild(body);
    try {
      const sims = await Promise.all(state.sel.map((sid) => getSim(store.run, sid)));
      clear(body);
      if (sims.length === 2 && state.diff) {
        if (state.showReason)
          body.appendChild(h("div", { class: "cols" }, reasonBlock(sims[0]), reasonBlock(sims[1])));
        body.appendChild(h("div", { class: "diffscroll" }, DiffView(sims[0], sims[1], state.hideEqual, () => { state.hideEqual = false; renderMain(); })));
      } else if (sims.length === 2) {
        body.appendChild(h("div", { class: "cols" }, tracePanel(sims[0]), tracePanel(sims[1])));
      } else {
        body.appendChild(tracePanel(sims[0]));
      }
    } catch (e) {
      clear(body);
      body.appendChild(h("div", { class: "error" }, "Failed to load trace: " + e.message));
    }
  }

  // seed open cluster for any deep-linked selection
  state.sel.forEach((sid) => {
    const c = s.clusters.find((x) => x.sims.includes(sid));
    if (c) openClusters.add(c.id);
  });
  buildLeft();
  renderMain();
  return wrap;
}
