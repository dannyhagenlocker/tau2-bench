import { clear, h } from "../dom.js";
import { getSim } from "../api.js";
import { store } from "../store.js";
import { parseHash } from "../router.js";
import { importanceBar, mechanism, spinner } from "../components/widgets.js";
import { Waterfall } from "../components/waterfall.js";
import { DiffView } from "../components/diff.js";

const MAX_SEL = 2; // comparison is pairwise (diff needs exactly two)

export function TracesPage() {
  const s = store.summary;
  const { params } = parseHash();
  const sel = [params.get("a"), params.get("b")].filter(Boolean).slice(0, MAX_SEL);
  const state = {
    sel,
    diff: params.get("diff") === "1" && sel.length === 2,
    hideEqual: false,
    showReason: false,
    mode: "clusters", // 'clusters' | 'tasks'
    taskFilter: "all", // all | passed | flaky | failed
  };
  const openClusters = new Set();
  const openTasks = new Set();
  let filter = "";

  // ---- derived: sims grouped by task; flaky lookup ----
  const byTask = {};
  for (const [sid, m] of Object.entries(s.sims)) {
    (byTask[m.task_id] = byTask[m.task_id] || []).push(sid);
  }
  for (const t of Object.keys(byTask)) {
    byTask[t].sort((a, b) => (s.sims[a].trial ?? 0) - (s.sims[b].trial ?? 0));
  }
  const taskIds = Object.keys(byTask).sort((a, b) => {
    const na = Number(a), nb = Number(b);
    return Number.isNaN(na) || Number.isNaN(nb) ? String(a).localeCompare(b) : na - nb;
  });
  const flakyByTask = {};
  (s.flaky || []).forEach((f) => (flakyByTask[f.task_id] = f));

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
  function compare(a, b, diff) {
    state.sel = [a, b];
    state.diff = !!diff;
    renderMain();
    buildLeft();
  }

  // ---------- shared member row ----------
  function memberRow(sid, primaryText, showMech = true) {
    const m = s.sims[sid];
    if (!m) return null;
    const inSel = state.sel.includes(sid);
    const full = state.sel.length >= MAX_SEL;
    return h(
      "div",
      { class: "member" + (inSel ? " sel" : "") },
      showMech ? mechanism(m.mechanism) : null,
      h("span", { class: "lbl" }, primaryText),
      h(
        "span",
        {
          class: "addbtn" + (inSel ? " on" : ""),
          title: inSel ? "remove from view" : full ? "view is full (max 2)" : "add to comparison",
          onClick: () => (inSel ? remove(sid) : add(sid)),
        },
        inSel ? "✓" : "+",
      ),
    );
  }

  // ---------- left: segmented control + toggle ----------
  function segmented() {
    const seg = h("div", { class: "seg" });
    [["clusters", "Clusters"], ["tasks", "Tasks"]].forEach(([m, label]) => {
      seg.appendChild(
        h(
          "button",
          {
            class: state.mode === m ? "on" : "",
            onClick: () => { state.mode = m; buildLeft(); },
          },
          label,
        ),
      );
    });
    return seg;
  }

  function taskStatus(sims) {
    const passN = sims.filter((sid) => s.sims[sid].reward >= 0.999).length;
    const kind = passN === sims.length ? "pass" : passN === 0 ? "fail" : "flaky";
    return { passN, total: sims.length, kind };
  }

  function taskFilterBar() {
    const opts = [["all", "All"], ["passed", "Passed"], ["flaky", "Flaky"], ["failed", "Failed"]];
    return h(
      "div",
      { class: "filter-pills" },
      ...opts.map(([v, label]) =>
        h(
          "button",
          {
            class: `fpill ${v}` + (state.taskFilter === v ? " on" : ""),
            onClick: () => { state.taskFilter = v; buildLeft(); },
          },
          label,
        ),
      ),
    );
  }

  // outcome kind ('pass'/'fail'/'flaky') that a filter value selects
  const FILTER_KIND = { passed: "pass", failed: "fail", flaky: "flaky" };

  function buildClusters(container, f) {
    container.appendChild(h("div", { class: "sec-title" }, `Failure clusters (${s.clusters.length})`));
    const totalFailures = Math.max(1, s.clusters.reduce((a, c) => a + c.count, 0));
    s.clusters.forEach((c) => {
      const hay = (c.id + " " + c.failure_type + " " + c.gloss + " " + c.signature + " " +
        c.sims.map((x) => s.sims[x] && s.sims[x].task_id).join(" ")).toLowerCase();
      if (f && !hay.includes(f)) return;
      const share = (c.count / totalFailures) * 100;
      const isOpen = openClusters.has(c.id);
      const head = h(
        "div",
        {
          class: "clu-head",
          onClick: () => { isOpen ? openClusters.delete(c.id) : openClusters.add(c.id); buildLeft(); },
        },
        h("span", { class: "caret" }, isOpen ? "▾" : "▸"),
        h("span", { class: "cl-id" }, c.id),
        h("span", { class: "cl-count" }, `${c.count} · ${share.toFixed(0)}%`),
      );
      const box = h("div", { class: "clu-box" }, head);
      box.appendChild(importanceBar(c.sims.map((sid) => (s.sims[sid] || {}).mechanism || "other"), totalFailures, c.count));
      if (isOpen) {
        if (c.summary || c.gloss) box.appendChild(h("div", { class: "cl-summary-mini" }, c.summary || c.gloss));
        const sortedSims = [...c.sims].sort((a, b) => {
          const ma = s.sims[a] || {}, mb = s.sims[b] || {};
          const ta = Number(ma.task_id), tb = Number(mb.task_id);
          const byTaskId = Number.isNaN(ta) || Number.isNaN(tb)
            ? String(ma.task_id).localeCompare(String(mb.task_id))
            : ta - tb;
          return byTaskId || (ma.trial ?? 0) - (mb.trial ?? 0);
        });
        sortedSims.forEach((sid) => {
          const m = s.sims[sid];
          // mechanism (failure taxonomy) belongs on each task, not the mixed cluster
          box.appendChild(memberRow(sid, `task ${m.task_id} · t${m.trial} · r=${m.reward.toFixed(1)}`, true));
        });
      }
      container.appendChild(box);
    });
  }

  function buildTasks(container, f) {
    taskIds.forEach((task) => {
      const sims = byTask[task];
      const { passN, total, kind } = taskStatus(sims);
      if (state.taskFilter !== "all" && kind !== FILTER_KIND[state.taskFilter]) return;
      if (f && !String(task).toLowerCase().includes(f)) return;
      const isFlaky = !!flakyByTask[task];
      const isOpen = openTasks.has(task);
      const head = h(
        "div",
        {
          class: "clu-head",
          onClick: () => { isOpen ? openTasks.delete(task) : openTasks.add(task); buildLeft(); },
        },
        h("span", { class: "caret" }, isOpen ? "▾" : "▸"),
        h("span", { class: "cl-id" }, "task " + task),
        h("span", { class: "taskstat " + kind, title: `${passN} of ${total} trials passed` }, `${passN}/${total} passed`),
        isFlaky ? h("span", { class: "flakytag", title: "flaky: some trials pass, some fail" }, "⚡") : null,
      );
      const box = h("div", { class: "clu-box" }, head);
      if (isOpen) {
        if (isFlaky) {
          const fl = flakyByTask[task];
          box.appendChild(
            h(
              "div",
              { class: "task-quick" },
              h("button", { class: "btn small", onClick: () => compare(fl.pass_sim, fl.fail_sim, true) }, "diff pass ↔ fail"),
            ),
          );
        } else if (sims.length >= 2) {
          box.appendChild(
            h(
              "div",
              { class: "task-quick" },
              h("button", { class: "btn small", onClick: () => compare(sims[0], sims[1], true) }, "diff trial 0 ↔ 1"),
            ),
          );
        }
        sims.forEach((sid) => {
          const m = s.sims[sid];
          box.appendChild(memberRow(sid, `trial ${m.trial} · r=${m.reward.toFixed(1)}`));
        });
      }
      container.appendChild(box);
    });
  }

  function buildLeft() {
    clear(left);
    const head = h("div", { class: "picker-head" });
    head.appendChild(
      h("input", {
        class: "search",
        placeholder: state.mode === "tasks" ? "filter tasks…" : "filter clusters / tasks / gloss…",
        value: filter,
        oninput: (e) => { filter = e.target.value; buildLeft(); left.querySelector(".search").focus(); },
      }),
    );
    head.appendChild(segmented());
    if (state.mode === "tasks") {
      head.appendChild(
        h(
          "div",
          { class: "task-tools" },
          taskFilterBar(),
          h("span", { class: "muted tiny" }, `${taskIds.length} tasks · ${(s.flaky || []).length} flaky`),
        ),
      );
    }
    left.appendChild(head);

    const body = h("div", { class: "picker-body" });
    left.appendChild(body);
    const f = filter.toLowerCase();
    if (state.mode === "tasks") buildTasks(body, f);
    else buildClusters(body, f);
  }

  // ---------- main ----------
  function chip(sid) {
    const m = s.sims[sid] || {};
    return h(
      "div",
      { class: "chip" },
      h("span", { class: "mono" }, (sid || "").slice(0, 8)),
      ` · task ${m.task_id} t${m.trial} `,
      mechanism(m.mechanism),
      ` r=${(m.reward ?? 0).toFixed(2)}`,
      h("span", { class: "chip-x", title: "remove from view", onClick: () => remove(sid) }, "✕"),
    );
  }

  function controls() {
    const two = state.sel.length === 2;
    const sameTask = two && s.sims[state.sel[0]] && s.sims[state.sel[1]] && s.sims[state.sel[0]].task_id === s.sims[state.sel[1]].task_id;
    const btn = (label, on, active, disabled) =>
      h("button", { class: "btn" + (active ? " active" : ""), disabled, onClick: on }, label);
    return h(
      "div",
      { class: "controls" },
      ...state.sel.map(chip),
      two && !sameTask ? h("span", { class: "warn tiny", title: "the two selected traces are from different tasks" }, "⚠ different tasks") : null,
      btn("Diff", () => { state.diff = !state.diff; renderMain(); }, state.diff, !two),
      btn("Hide equal", () => { state.hideEqual = !state.hideEqual; renderMain(); }, state.hideEqual, !(two && state.diff)),
      btn("Failure reason", () => { state.showReason = !state.showReason; renderMain(); }, state.showReason, !state.sel.length),
      btn("Clear", clearAll, false, !state.sel.length),
    );
  }

  function reasonBlock(sim) {
    const fr = sim.failure_reason;
    if (!fr) return null;
    const rows = [
      h("div", { class: "rr-line" }, h("b", {}, "mechanism "), mechanism(sim.mechanism)),
      h("div", { class: "rr-line" }, h("b", {}, "reward "), fr.reward.toFixed(2), " · basis ", (fr.reward_basis || []).join(" + ")),
    ];
    const bd = Object.entries(fr.reward_breakdown || {}).map(([k, v]) => `${k}=${v}`).join("   ");
    if (bd) rows.push(h("div", { class: "rr-line mono tiny" }, bd));
    if (fr.termination_reason && fr.termination_reason !== "user_stop")
      rows.push(h("div", { class: "rr-line" }, h("b", {}, "termination "), fr.termination_reason));
    if (sim.db_diff_signature) {
      rows.push(h("div", { class: "rr-line" }, h("b", {}, "DB diff "), sim.db_gloss || ""));
      rows.push(h("div", { class: "rr-line mono tiny breakall muted" }, sim.db_diff_signature));
    }
    (fr.nl_failures || []).forEach((n) =>
      rows.push(h("div", { class: "rr-nl" }, h("div", { class: "rr-assert" }, "✗ " + n.assertion), n.justification ? h("div", { class: "rr-just" }, n.justification) : null)),
    );
    (fr.communicate_failures || []).forEach((n) =>
      rows.push(h("div", { class: "rr-nl" }, h("div", { class: "rr-assert" }, "✗ communicate: " + n.info), n.justification ? h("div", { class: "rr-just" }, n.justification) : null)),
    );
    if (rows.length <= 1 && !sim.db_diff_signature)
      rows.push(h("div", { class: "muted small" }, sim.reward >= 0.999 ? "Passed — no failure." : "No structured failure reason recorded."));
    return h("div", { class: "reason" }, h("div", { class: "reason-title" }, sim.reward >= 0.999 ? "Evaluation" : "Golden failure reason"), ...rows);
  }

  function tracePanel(sim) {
    const cap = h(
      "div",
      { class: "wfcap" },
      h("span", {}, [
        h("span", { class: "mono" }, sim.simulation_id.slice(0, 8)),
        ` · task ${sim.task_id} · t${sim.trial} · `,
        mechanism(sim.mechanism),
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
      main.appendChild(h("div", { class: "empty" }, "Add a trace with + from a cluster or task on the left. Use the Tasks tab to compare trials of the same task."));
      return;
    }
    const body = h("div", { class: "trace-body" }, spinner("Loading trace…"));
    main.appendChild(body);
    try {
      const sims = await Promise.all(state.sel.map((sid) => getSim(store.run, sid)));
      clear(body);
      if (sims.length === 2 && state.diff) {
        if (state.showReason) body.appendChild(h("div", { class: "cols" }, reasonBlock(sims[0]), reasonBlock(sims[1])));
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

  // seed: open the cluster/task of any deep-linked selection
  state.sel.forEach((sid) => {
    const m = s.sims[sid];
    if (m) openTasks.add(m.task_id);
    const c = s.clusters.find((x) => x.sims.includes(sid));
    if (c) openClusters.add(c.id);
  });
  buildLeft();
  renderMain();
  return wrap;
}
