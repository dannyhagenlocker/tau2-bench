import { clear, h } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { badge } from "../components/widgets.js";

export function ProposalsPage() {
  const wrap = h("div", { class: "page" });
  const body = h("div", { class: "cmp-sections" });
  wrap.appendChild(body);
  load();
  return wrap;

  async function load() {
    clear(body);
    body.appendChild(h("div", { class: "spinner" }, "Loading proposals…"));
    try {
      const [lineages, proposals] = await Promise.all([api.lineages(), api.proposals(store.run)]);
      clear(body);
      body.appendChild(newProposalPanel());
      body.appendChild(lineagesPanel(lineages));
      body.appendChild(proposalsPanel(proposals));
    } catch (e) {
      clear(body);
      body.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
    }
  }

  // ---- create ----
  function newProposalPanel() {
    const clusters = (store.summary && store.summary.clusters) || [];
    const clusterSel = h(
      "select",
      { class: "select", style: { maxWidth: "380px" } },
      ...clusters.map((c) => h("option", { value: c.id }, `${c.id} · ${c.gloss || c.failure_type} (n=${c.count})`)),
    );
    const coderSel = h(
      "select",
      { class: "select" },
      ...["auto", "openai", "claude", "cursor", "manual"].map((v) => h("option", { value: v }, v)),
    );
    const modelIn = h("input", { class: "search", style: { maxWidth: "160px" }, placeholder: "gpt-4.1" });
    const lineageIn = h("input", { class: "search", style: { maxWidth: "160px" }, placeholder: store.run });
    const evalChk = h("input", { type: "checkbox" });
    const out = h("div", {});
    const btn = h("button", { class: "btn active" }, "Create proposal");

    btn.addEventListener("click", async () => {
      if (!clusters.length) return;
      btn.disabled = true;
      const prevText = btn.textContent;
      btn.textContent = evalChk.checked ? "Proposing + evaluating…" : "Proposing…";
      clear(out);
      out.appendChild(h("div", { class: "spinner" }, "Running coder in an isolated worktree…"));
      try {
        const res = await api.propose(store.run, {
          cluster: clusterSel.value,
          coder: coderSel.value,
          coder_model: modelIn.value.trim() || null,
          lineage: lineageIn.value.trim() || null,
          do_eval: evalChk.checked,
        });
        clear(out);
        out.appendChild(cliResult(res));
        if (res.ok) setTimeout(load, 400);
      } catch (e) {
        clear(out);
        out.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
      } finally {
        btn.disabled = false;
        btn.textContent = prevText;
      }
    });

    return h(
      "div",
      { class: "panel" },
      h("h3", {}, "New proposal"),
      h("div", { class: "muted tiny", style: { marginBottom: "8px" } }, "One failure cluster → one auto-coded, allowlisted harness edit on an isolated lineage worktree."),
      h("div", { class: "form-row" }, h("label", {}, "cluster"), clusterSel),
      h("div", { class: "form-row" }, h("label", {}, "coder"), coderSel, h("label", {}, "proposer model"), modelIn, h("label", {}, "lineage"), lineageIn),
      h("div", { class: "form-row" }, h("label", { style: { minWidth: "auto" } }, evalChk, " run subset eval")),
      evalChk && h("div", { class: "warn-box" }, "Eval spends OpenAI budget (~$1–3) and runs tau2 for minutes. Leave off for a free draft (branch + diff + coder log)."),
      h("div", { class: "form-row" }, btn),
      out,
    );
  }

  // ---- lineages ----
  function lineagesPanel(data) {
    const lins = (data && data.lineages) || [];
    const panel = h("div", { class: "panel" }, h("h3", {}, `Lineages (${lins.length})`));
    if (!lins.length) {
      panel.appendChild(h("div", { class: "muted" }, "No lineages yet — create and accept a proposal to start one."));
      return panel;
    }
    const tbl = h("table", { class: "tbl" }, h("tr", {}, h("th", {}, "lineage"), h("th", {}, "branch"), h("th", {}, "base → tip"), h("th", {}, "gen"), h("th", {}, "accepted")));
    lins.forEach((l) => {
      const accepted = (l.accepted_proposals || []).map((p) => p.cluster_id).join(", ") || "—";
      tbl.appendChild(
        h("tr", {},
          h("td", { class: "mono" }, l.lineage_id),
          h("td", { class: "mono tiny" }, l.branch),
          h("td", { class: "mono tiny" }, `${(l.base_commit || "").slice(0, 8)} → ${(l.tip_commit || "").slice(0, 8)}`),
          h("td", {}, l.generation),
          h("td", { class: "tiny" }, accepted),
        ),
      );
    });
    panel.appendChild(tbl);
    return panel;
  }

  // ---- proposals list + detail ----
  function proposalsPanel(data) {
    const props = (data && data.proposals) || [];
    const panel = h("div", { class: "panel" }, h("h3", {}, `Proposals — ${store.run} (${props.length})`));
    const detail = h("div", { class: "prop-detail" });
    if (!props.length) {
      panel.appendChild(h("div", { class: "muted" }, "No proposals yet for this run."));
      return panel;
    }
    const tbl = h("table", { class: "tbl" }, h("tr", {}, h("th", {}, "proposal"), h("th", {}, "cluster"), h("th", {}, "status"), h("th", {}, "verdict"), h("th", {}, "coder"), h("th", {}, "diff"), h("th", {}, "summary")));
    props.forEach((p) => {
      tbl.appendChild(
        h("tr", { class: "prop-row", onClick: () => openDetail(p.proposal_id, detail) },
          h("td", { class: "mono tiny" }, p.proposal_id),
          h("td", {}, p.cluster_id),
          h("td", {}, statusPill(p.status)),
          h("td", {}, p.eval_verdict ? verdictPill(p.eval_verdict) : "—"),
          h("td", { class: "tiny" }, p.coder_backend || "—"),
          h("td", { class: "tiny" }, p.diff_stat || "—"),
          h("td", { class: "tiny muted" }, p.one_line_summary || ""),
        ),
      );
    });
    panel.appendChild(tbl);
    panel.appendChild(detail);
    return panel;
  }

  async function openDetail(pid, container) {
    clear(container);
    container.appendChild(h("div", { class: "spinner" }, "Loading proposal…"));
    try {
      const d = await api.proposal(store.run, pid);
      clear(container);
      container.appendChild(renderDetail(d));
    } catch (e) {
      clear(container);
      container.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
    }
  }

  function renderDetail(d) {
    const m = d.metadata || {};
    const cl = d.coder_log || {};
    const box = h("div", { class: "prop-detail-box" });

    const actions = h("div", { class: "form-row" });
    if (m.status === "draft" || m.status === "evaluated") {
      const accept = h("button", { class: "btn active" }, "Accept → squash onto lineage");
      const reject = h("button", { class: "btn" }, "Reject");
      const aout = h("div", {});
      accept.addEventListener("click", () => runAction(api.accept, d.proposal_id, aout, accept, reject));
      reject.addEventListener("click", () => runAction(api.reject, d.proposal_id, aout, accept, reject));
      actions.appendChild(accept);
      actions.appendChild(reject);
      actions.appendChild(aout);
    }

    box.appendChild(
      h("div", { class: "panel-head" },
        h("h3", {}, `${d.proposal_id} · ${m.cluster_id || ""}`),
        h("span", {}, [statusPill(m.status), m.eval_verdict ? verdictPill(m.eval_verdict) : null]),
      ),
    );
    box.appendChild(h("div", { class: "muted tiny" }, `lineage ${m.lineage_id || "—"} · branch ${m.branch_name || "—"} · coder ${m.coder_backend || "—"} · diff ${m.diff_stat || "none"}`));

    // coder log — proposer model + cost + edits (the budget-ledger record)
    box.appendChild(h("h4", { class: "prop-h4" }, "Coder"));
    box.appendChild(h("div", { class: "rr-line" }, `backend ${cl.backend || "—"} · model ${cl.model || "—"} · cost ${cl.cost != null ? "$" + Number(cl.cost).toFixed(4) : "—"} · ${cl.ok ? "ok" : "failed"}`));
    if (cl.summary) box.appendChild(h("div", { class: "rr-line" }, cl.summary));
    if (cl.error) box.appendChild(h("div", { class: "error tiny" }, cl.error));
    if (cl.edited_paths && cl.edited_paths.length) box.appendChild(h("div", { class: "badges" }, ...cl.edited_paths.map((p) => badge(p, "mono"))));

    // subset eval
    if (d.subset_results) {
      const sr = d.subset_results;
      box.appendChild(h("h4", { class: "prop-h4" }, "Subset eval"));
      box.appendChild(h("div", { class: "rr-line" }, [verdictPill(sr.verdict), " ", sr.recommendation || ""]));
      const t = h("table", { class: "tbl" }, h("tr", {}, h("th", {}, "task"), h("th", {}, "role"), h("th", {}, "base"), h("th", {}, "cand"), h("th", {}, "Δ")));
      (sr.tasks || []).forEach((x) =>
        t.appendChild(h("tr", {}, h("td", {}, x.task_id), h("td", { class: "tiny" }, x.role), h("td", {}, x.baseline_reward.toFixed(2)), h("td", {}, x.candidate_reward.toFixed(2)), h("td", { class: x.delta >= 0 ? "up" : "down" }, (x.delta >= 0 ? "+" : "") + x.delta.toFixed(2)))),
      );
      box.appendChild(t);
    }

    // diff
    if (d.diff && d.diff.trim()) {
      box.appendChild(h("h4", { class: "prop-h4" }, "Diff"));
      box.appendChild(h("pre", { class: "diffpre" }, d.diff));
    }

    if (actions.childNodes.length) box.appendChild(actions);
    return box;
  }

  async function runAction(fn, pid, out, ...btns) {
    btns.forEach((b) => (b.disabled = true));
    clear(out);
    out.appendChild(h("div", { class: "spinner" }, "Running…"));
    try {
      const res = await fn(store.run, pid);
      clear(out);
      out.appendChild(cliResult(res));
      if (res.ok) setTimeout(load, 400);
    } catch (e) {
      clear(out);
      out.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
    } finally {
      btns.forEach((b) => (b.disabled = false));
    }
  }
}

// ---- small helpers ----
function statusPill(s) {
  return h("span", { class: "pstatus " + (s || "draft") }, s || "draft");
}
function verdictPill(v) {
  return h("span", { class: "verdict " + v }, v);
}
function cliResult(res) {
  const wrap = h("div", {});
  wrap.appendChild(h("div", { class: res.ok ? "up" : "down" }, res.ok ? "✓ done" : `✗ failed (exit ${res.returncode})`));
  const text = (res.stdout || "") + (res.stderr ? "\n" + res.stderr : "");
  if (text.trim()) wrap.appendChild(h("pre", { class: "cli-out" }, text.trim()));
  return wrap;
}
