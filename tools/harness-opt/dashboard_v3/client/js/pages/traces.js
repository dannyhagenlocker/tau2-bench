import { clear, h } from "../dom.js";
import { getSim } from "../api.js";
import { store } from "../store.js";
import { parseHash } from "../router.js";
import { badge, ftype, spinner } from "../components/widgets.js";
import { Waterfall } from "../components/waterfall.js";
import { DiffView } from "../components/diff.js";

export function TracesPage() {
  const s = store.summary;
  const { params } = parseHash();
  const state = {
    a: params.get("a") || null,
    b: params.get("b") || null,
    diff: params.get("diff") === "1",
    hideEqual: false,
  };
  const openClusters = new Set();
  let filter = "";

  const wrap = h("div", { class: "page traces" });
  const left = h("div", { class: "panel trace-picker" });
  const main = h("div", { class: "trace-main" });
  wrap.appendChild(h("div", { class: "grid-tr" }, left, main));

  // ---------- selection helpers ----------
  function pick(slot, sid) {
    if (slot === "b" && state.a === sid) return;
    state[slot] = sid;
    renderMain();
    buildLeft();
  }
  function loadFlaky(f) {
    state.a = f.pass_sim;
    state.b = f.fail_sim;
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
            h("span", { class: "go" }, "pass↔fail →"),
          ),
        );
      });
    }

    left.appendChild(h("div", { class: "sec-title" }, `Clusters (${s.clusters.length})`));
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
          box.appendChild(
            h(
              "div",
              { class: `member ${state.a === sid ? "sel-a" : ""} ${state.b === sid ? "sel-b" : ""}` },
              h("span", { class: "lbl" }, `task ${m.task_id} · t${m.trial} · r=${m.reward.toFixed(1)}`),
              h("span", { class: "pill " + (state.a === sid ? "on-a" : ""), onClick: () => pick("a", sid) }, "A"),
              h("span", { class: "pill " + (state.b === sid ? "on-b" : ""), onClick: () => pick("b", sid) }, "B"),
            ),
          );
        });
      }
      left.appendChild(box);
    });
  }

  // ---------- main ----------
  function slotHeader(slot, sid) {
    const tagColor = slot === "a" ? "#2563eb" : "#db2777";
    if (!sid) return h("div", { class: "slot" }, h("span", { class: "tag", style: { color: tagColor } }, slot.toUpperCase()), h("i", {}, " none"));
    const m = s.sims[sid] || {};
    const badges = [];
    if (m.db_diff_signature) badges.push(badge("db: " + m.db_diff_signature, "mono"));
    if (m.nl_failure_signature) badges.push(badge("nl: " + m.nl_failure_signature));
    (m.flags || []).forEach((fl) => badges.push(badge(fl)));
    return h(
      "div",
      { class: "slot" },
      h("span", { class: "tag", style: { color: tagColor } }, slot.toUpperCase()),
      h("span", { class: "mono" }, (sid || "").slice(0, 8)),
      ` · task ${m.task_id} · t${m.trial} · `,
      ftype(m.failure_type),
      ` · r=${(m.reward ?? 0).toFixed(2)}`,
      h("div", { class: "badges" }, ...badges),
    );
  }

  function controls() {
    const both = state.a && state.b;
    const btn = (label, on, active, disabled) =>
      h("button", { class: "btn" + (active ? " active" : ""), disabled: disabled, onClick: on }, label);
    return h(
      "div",
      { class: "controls" },
      slotHeader("a", state.a),
      slotHeader("b", state.b),
      btn("⇄ Swap", () => { [state.a, state.b] = [state.b, state.a]; renderMain(); buildLeft(); }, false, !both),
      btn("Clear B", () => { state.b = null; state.diff = false; renderMain(); buildLeft(); }, false, !state.b),
      btn("Diff", () => { state.diff = !state.diff; renderMain(); }, state.diff, !both),
      btn("Hide equal", () => { state.hideEqual = !state.hideEqual; renderMain(); }, state.hideEqual, !(both && state.diff)),
    );
  }

  function panelWaterfall(sim) {
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
    return h("div", { class: "panel" }, cap, Waterfall(sim));
  }

  async function renderMain() {
    clear(main);
    main.appendChild(controls());
    if (!state.a) {
      main.appendChild(h("div", { class: "empty" }, "Pick a trace (A), or load a flaky pass↔fail pair on the left."));
      return;
    }
    const body = h("div", { class: "trace-body" }, spinner("Loading trace…"));
    main.appendChild(body);
    try {
      const simA = await getSim(store.run, state.a);
      const simB = state.b ? await getSim(store.run, state.b) : null;
      clear(body);
      if (!simB) body.appendChild(panelWaterfall(simA));
      else if (state.diff)
        body.appendChild(DiffView(simA, simB, state.hideEqual, () => { state.hideEqual = false; renderMain(); }));
      else body.appendChild(h("div", { class: "cols" }, panelWaterfall(simA), panelWaterfall(simB)));
    } catch (e) {
      clear(body);
      body.appendChild(h("div", { class: "error" }, "Failed to load trace: " + e.message));
    }
  }

  // seed open cluster if deep-linked to a member
  if (state.a) {
    const c = s.clusters.find((x) => x.sims.includes(state.a));
    if (c) openClusters.add(c.id);
  }
  buildLeft();
  renderMain();
  return wrap;
}
