import { clear, h, hs } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { badge } from "../components/widgets.js";
import { openModal } from "../components/modal.js";
import { diffEditor } from "../components/editor.js";

function warnIcon() {
  return hs(
    "svg",
    { viewBox: "0 0 24 24", width: "13", height: "13", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round" },
    hs("path", { d: "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" }),
    hs("path", { d: "M12 9v4" }),
    hs("path", { d: "M12 17h.01" }),
  );
}

function trashIcon() {
  return hs(
    "svg",
    { viewBox: "0 0 24 24", width: "15", height: "15", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round" },
    hs("path", { d: "M3 6h18" }),
    hs("path", { d: "M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" }),
    hs("path", { d: "M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14" }),
    hs("path", { d: "M10 11v6" }),
    hs("path", { d: "M14 11v6" }),
  );
}

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
    const clusters = [...((store.summary && store.summary.clusters) || [])].sort((a, b) => b.count - a.count);
    const optText = (c) => {
      const sum = (c.summary || c.gloss || c.mechanism || "").replace(/\s+/g, " ").trim();
      const short = sum.length > 60 ? sum.slice(0, 60) + "…" : sum;
      return `${c.id} · ${c.count} sims${short ? " — " + short : ""}`;
    };
    const clusterSel = h(
      "select",
      { class: "select", style: { maxWidth: "480px" } },
      ...clusters.map((c) => h("option", { value: c.id, title: c.summary || "" }, optText(c))),
    );
    const clusterSummary = h("div", { class: "cl-summary prop-cluster-summary" });
    const updateSummary = () => {
      const c = clusters.find((x) => x.id === clusterSel.value);
      clusterSummary.textContent = c ? c.summary || c.gloss || "" : "";
    };
    clusterSel.addEventListener("change", updateSummary);
    const coderSel = h(
      "select",
      { class: "select" },
      ...["auto", "openai", "claude", "cursor", "manual"].map((v) => h("option", { value: v }, v)),
    );
    const modelIn = h("input", { class: "search", style: { maxWidth: "160px" }, placeholder: "gpt-4.1" });
    const lineageIn = h("input", { class: "search", style: { maxWidth: "160px" }, placeholder: store.run });
    const evalChk = h("input", { type: "checkbox", class: "switch-input" });
    const evalToggle = h(
      "label",
      { class: "switch" },
      evalChk,
      h("span", { class: "switch-track" }, h("span", { class: "switch-thumb" })),
      h("span", { class: "switch-label" }, "Run subset eval"),
    );
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

    const panel = h(
      "div",
      { class: "panel" },
      h("h3", {}, "New proposal"),
      h("div", { class: "muted tiny", style: { marginBottom: "8px" } }, "One failure cluster → one auto-coded, allowlisted harness edit on an isolated lineage worktree."),
      h("div", { class: "form-row" }, h("label", {}, "cluster"), clusterSel),
      clusterSummary,
      h("div", { class: "form-row" }, h("label", {}, "coder"), coderSel, h("label", {}, "proposer model"), modelIn, h("label", {}, "lineage"), lineageIn),
      h(
        "div",
        { class: "form-row eval-row" },
        evalToggle,
        h("span", { class: "eval-note" }, warnIcon(), " Eval spends OpenAI budget (~$1–3) and runs tau2 for minutes. Leave off for a free draft (branch + diff + coder log)."),
      ),
      h("div", { class: "form-row", style: { marginTop: "16px" } }, btn),
      out,
    );
    updateSummary();
    return panel;
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
    if (!props.length) {
      panel.appendChild(h("div", { class: "muted" }, "No proposals yet for this run."));
      return panel;
    }
    const tbl = h("table", { class: "tbl" }, h("tr", {}, h("th", {}, "proposal"), h("th", {}, "cluster"), h("th", {}, "status"), h("th", {}, "verdict"), h("th", {}, "coder"), h("th", {}, "diff"), h("th", {}, "summary")));
    props.forEach((p) => {
      const tr = h("tr", {
        class: "prop-row",
        onClick: () => openProposalModal(p.proposal_id),
      },
        h("td", { class: "mono tiny" }, p.proposal_id),
        h("td", {}, p.cluster_id),
        h("td", {}, statusPill(p.status)),
        h("td", {}, p.eval_verdict ? verdictPill(p.eval_verdict) : "—"),
        h("td", { class: "tiny" }, p.coder_backend || "—"),
        h("td", { class: "tiny" }, p.diff_stat || "—"),
        h("td", { class: "tiny muted" }, p.one_line_summary || ""),
      );
      tbl.appendChild(tr);
    });
    panel.appendChild(tbl);
    return panel;
  }

  // ---- modal: click a proposal → tabbed modal (Overview + Edit diff) ----
  function openProposalModal(pid) {
    const modal = openModal({
      title: pid,
      subtitle: store.run,
      onClose: () => load(),
      tabs: [
        {
          id: "overview",
          label: "Overview",
          render: () => {
            const c = h("div", { class: "prop-modal-ov" });
            loadOverview(c);
            return c;
          },
        },
        { id: "editor", label: "Edit diff", render: () => renderEditorTab(pid) },
      ],
    });

    async function loadOverview(container) {
      clear(container);
      container.appendChild(h("div", { class: "spinner" }, "Loading proposal…"));
      try {
        const d = await api.proposal(store.run, pid);
        clear(container);
        container.appendChild(
          renderDetail(d, { refresh: () => loadOverview(container), close: modal.close }),
        );
      } catch (e) {
        clear(container);
        container.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
      }
    }

    function renderEditorTab(id) {
      const c = h("div", { class: "prop-editor" });
      const scroll = h("div", { class: "prop-editor-scroll" });
      const foot = h("div", { class: "prop-editor-foot" });
      c.appendChild(scroll);
      c.appendChild(foot);
      scroll.appendChild(h("div", { class: "spinner" }, "Loading files…"));
      const editors = [];
      api
        .proposalFiles(store.run, id)
        .then((res) => {
          clear(scroll);
          clear(foot);
          const files = (res && res.files) || [];
          if (!files.length) {
            scroll.appendChild(h("div", { class: "muted" }, "No changed files to edit (draft has no diff yet)."));
            return;
          }
          files.forEach((f) => {
            scroll.appendChild(h("div", { class: "editor-file-head mono tiny" }, f.path + (f.new_file ? "  (new file)" : "")));
            const ed = diffEditor(f.original || "", f.modified || "", { language: langFor(f.path) });
            editors.push({ path: f.path, ed });
            scroll.appendChild(ed.node);
          });
          const out = h("div", {});
          const saveBtn = h("button", { class: "btn active" }, "Save edits → re-commit");
          saveBtn.addEventListener("click", async () => {
            saveBtn.disabled = true;
            clear(out);
            out.appendChild(h("div", { class: "spinner" }, "Committing edit…"));
            try {
              const payload = {};
              editors.forEach((e) => (payload[e.path] = e.ed.getModified()));
              const r = await api.saveProposalFiles(store.run, id, payload);
              clear(out);
              out.appendChild(h("div", { class: "up" }, "✓ saved — diff " + (r.diff_stat || "") + ". Status reset to draft; re-run eval from Overview."));
              load();
            } catch (e) {
              clear(out);
              out.appendChild(h("div", { class: "error" }, "Save failed: " + e.message));
            } finally {
              saveBtn.disabled = false;
            }
          });
          foot.appendChild(
            h(
              "div",
              { class: "prop-ed-bar" },
              h("div", { class: "prop-ed-note muted tiny" }, "Edit the right pane. Only allowlisted harness files are editable; saving re-commits the proposal branch and invalidates the prior eval."),
              saveBtn,
            ),
          );
          foot.appendChild(out);
        })
        .catch((e) => {
          clear(scroll);
          clear(foot);
          scroll.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
        });
      return c;
    }
  }

  function renderDetail(d, ctx) {
    const m = d.metadata || {};
    const cl = d.coder_log || {};
    const box = h("div", { class: "prop-detail-box" });
    const scroll = h("div", { class: "prop-scroll" });
    box.appendChild(scroll);
    const editable = m.status === "draft" || m.status === "evaluated";
    const evaluating = m.status === "evaluating";
    const aout = h("div", {});

    // delete → trash icon in the top-right of the detail, away from the primary actions
    const del = h(
      "button",
      { class: "icon-btn danger", title: "Delete proposal (branch + artifacts)", "aria-label": "Delete proposal" },
      trashIcon(),
    );
    del.addEventListener("click", () => {
      if (!confirm(`Delete proposal ${d.proposal_id} (branch + artifacts)?`)) return;
      runAction(api.deleteProposal, d.proposal_id, aout, ctx, [del], true);
    });

    scroll.appendChild(
      h(
        "div",
        { class: "prop-head-row" },
        h("div", { class: "muted tiny" }, `${m.cluster_id || ""} · lineage ${m.lineage_id || "—"} · branch ${m.branch_name || "—"} · coder ${m.coder_backend || "—"} · diff ${m.diff_stat || "none"}`),
        del,
      ),
    );
    scroll.appendChild(h("div", { class: "prop-head-pills" }, statusPill(m.status), " ", m.eval_verdict ? verdictPill(m.eval_verdict) : null));

    if (evaluating) {
      scroll.appendChild(
        h(
          "div",
          { class: "eval-running" },
          h("span", { class: "eval-spin" }),
          h(
            "div",
            {},
            h("div", { class: "eval-running-title" }, "Evaluating…"),
            h("div", { class: "muted tiny" }, "Running tau2 on the subset server-side (a few minutes). Safe to close — it keeps running, and the log below refreshes automatically."),
          ),
        ),
      );
      if (ctx && ctx.refresh) {
        setTimeout(() => {
          if (document.body.contains(box)) ctx.refresh();
        }, 3000);
      }
    }
    if (evaluating || (d.eval_log && d.eval_log.trim())) {
      scroll.appendChild(h("h4", { class: "prop-h4" }, evaluating ? "Progress log" : "Eval log"));
      const logText = (d.eval_log || "").slice(-8000);
      const logPre = h("pre", { class: "cli-out" }, logText || "Waiting for the first output from tau2…");
      scroll.appendChild(logPre);
      requestAnimationFrame(() => {
        logPre.scrollTop = logPre.scrollHeight;
      });
    }

    // footer actions: run eval on the left, reject / accept on the right
    const leftG = h("div", { class: "prop-actions-l" });
    const rightG = h("div", { class: "prop-actions-r" });
    const actions = h("div", { class: "prop-actions" }, leftG, rightG);
    if (editable) {
      const runEval = h("button", { class: "btn" }, d.subset_results ? "Re-run eval" : "Run eval");
      const accept = h("button", { class: "btn active" }, "Accept → squash onto lineage");
      const reject = h("button", { class: "btn reject" }, "Reject");
      const grp = [runEval, accept, reject, del];
      runEval.addEventListener("click", () => {
        runEval.disabled = true;
        runEval.textContent = "Starting…";
        startEval(d.proposal_id, ctx);
      });
      accept.addEventListener("click", () => runAction(api.accept, d.proposal_id, aout, ctx, grp, true));
      reject.addEventListener("click", () => runAction(api.reject, d.proposal_id, aout, ctx, grp, true));
      leftG.appendChild(runEval);
      rightG.appendChild(reject);
      rightG.appendChild(accept);
    }

    // coder log — proposer model + cost + edits (the budget-ledger record)
    scroll.appendChild(h("h4", { class: "prop-h4" }, "Coder"));
    scroll.appendChild(h("div", { class: "rr-line" }, `backend ${cl.backend || "—"} · model ${cl.model || "—"} · cost ${cl.cost != null ? "$" + Number(cl.cost).toFixed(4) : "—"} · ${cl.ok ? "ok" : "failed"}`));
    if (cl.summary) scroll.appendChild(h("div", { class: "rr-line" }, cl.summary));
    if (cl.error) scroll.appendChild(h("div", { class: "error tiny" }, cl.error));
    if (cl.edited_paths && cl.edited_paths.length) scroll.appendChild(h("div", { class: "badges" }, ...cl.edited_paths.map((p) => badge(p, "mono"))));

    // subset eval
    if (d.subset_results) {
      const sr = d.subset_results;
      scroll.appendChild(h("h4", { class: "prop-h4" }, "Subset eval"));
      scroll.appendChild(h("div", { class: "rr-line" }, [verdictPill(sr.verdict), " ", sr.recommendation || ""]));
      const t = h("table", { class: "tbl" }, h("tr", {}, h("th", {}, "task"), h("th", {}, "role"), h("th", {}, "base"), h("th", {}, "cand"), h("th", {}, "Δ")));
      (sr.tasks || []).forEach((x) =>
        t.appendChild(h("tr", {}, h("td", {}, x.task_id), h("td", { class: "tiny" }, x.role), h("td", {}, x.baseline_reward.toFixed(2)), h("td", {}, x.candidate_reward.toFixed(2)), h("td", { class: x.delta >= 0 ? "up" : "down" }, (x.delta >= 0 ? "+" : "") + x.delta.toFixed(2)))),
      );
      scroll.appendChild(t);
    }

    // diff (read-only view; edit via the Edit diff tab)
    if (d.diff && d.diff.trim()) {
      scroll.appendChild(h("h4", { class: "prop-h4" }, "Diff"));
      scroll.appendChild(h("pre", { class: "diffpre" }, d.diff));
    }

    if (editable) {
      box.appendChild(h("div", { class: "prop-footer" }, actions, aout));
    } else {
      scroll.appendChild(aout);
    }
    return box;
  }

  function startEval(pid, ctx) {
    // FastAPI runs the (blocking) eval CLI in a threadpool, so status polling
    // keeps working while it runs. Fire it, then flip the modal into the
    // "evaluating" view (status is written server-side up front) rather than
    // freezing on a spinner — renderDetail then tails eval.log automatically.
    let done = false;
    api
      .evalProposal(store.run, pid)
      .catch(() => {})
      .finally(() => {
        done = true;
        if (ctx && ctx.refresh) ctx.refresh();
      });
    // Nudge into the evaluating view, retrying while the worktree/subprocess
    // spins up; renderDetail's own poll takes over once status is "evaluating".
    let tries = 0;
    const nudge = () => {
      if (done) return;
      if (ctx && ctx.refresh) ctx.refresh();
      if (++tries < 8) setTimeout(nudge, 900);
    };
    setTimeout(nudge, 600);
  }

  async function runAction(fn, pid, out, ctx, btns, closeOnDone) {
    btns.forEach((b) => (b.disabled = true));
    clear(out);
    out.appendChild(h("div", { class: "spinner" }, "Running… (eval can take minutes)"));
    try {
      const res = await fn(store.run, pid);
      clear(out);
      out.appendChild(cliResult(res));
      if (res.ok) {
        load();
        if (closeOnDone && ctx && ctx.close) setTimeout(ctx.close, 600);
        else if (ctx && ctx.refresh) setTimeout(ctx.refresh, 400);
      }
    } catch (e) {
      clear(out);
      out.appendChild(h("div", { class: "error" }, "Failed: " + e.message));
    } finally {
      btns.forEach((b) => (b.disabled = false));
    }
  }
}

function langFor(path) {
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".md")) return "markdown";
  if (path.endsWith(".json")) return "json";
  return "plaintext";
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
