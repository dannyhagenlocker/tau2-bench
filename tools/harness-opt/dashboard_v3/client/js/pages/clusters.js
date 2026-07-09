import { clear, h } from "../dom.js";
import { store } from "../store.js";
import { navigate, parseHash } from "../router.js";
import { MECH_ORDER, importanceBar, mechanism, mechanismColor } from "../components/widgets.js";

export function ClustersPage() {
  const s = store.summary;
  const wrap = h("div", { class: "page clusters" });
  const clusters = [...s.clusters].sort((a, b) => b.count - a.count);

  const detail = h("div", { class: "panel cluster-detail" });
  const list = h("div", { class: "panel cluster-list" });

  const memberMech = (sid) => (s.sims[sid] || {}).mechanism || "other";

  // per-cluster mechanism composition (membership is embedding-driven, so a
  // cluster can be mechanism-mixed — show the breakdown, not just the label)
  function mechComposition(c) {
    const counts = {};
    c.sims.forEach((sid) => { const m = memberMech(sid); counts[m] = (counts[m] || 0) + 1; });
    const total = c.sims.length || 1;
    const order = MECH_ORDER.filter((m) => counts[m]);
    const barEl = h("div", { class: "mechcomp" },
      ...order.map((m) => h("span", { title: `${m}: ${counts[m]}`, style: { width: (counts[m] / total) * 100 + "%", background: mechanismColor(m) } })));
    const legend = h("div", { class: "badges" },
      ...order.map((m) => h("span", { class: "leg" }, h("span", { class: "leg-dot", style: { background: mechanismColor(m) } }), `${m} ${counts[m]}`)));
    return h("div", {}, barEl, legend);
  }

  function showCluster(cid) {
    const c = clusters.find((x) => x.id === cid);
    clear(detail);
    if (!c) { detail.appendChild(h("div", { class: "muted" }, "Select a cluster.")); return; }
    const head = h("div", { class: "cluster-detail-head" });
    const bodyS = h("div", { class: "cluster-detail-body" });
    detail.appendChild(head);
    detail.appendChild(bodyS);

    head.appendChild(
      h("div", { class: "panel-head" },
        h("h3", {}, `Cluster ${c.id}`),
      ),
    );
    head.appendChild(h("div", { class: "cl-summary" }, c.summary || c.gloss || c.name));
    if (c.method) head.appendChild(h("div", { class: "muted tiny" }, `clustering method: ${c.method}`));

    const members = c.sims.map((sid) => s.sims[sid]).filter(Boolean);
    head.appendChild(h("div", { class: "muted small", style: { margin: "8px 0 0" } }, `${members.length} members · mechanism composition`));
    head.appendChild(mechComposition(c));

    // sort + filter state for the member table
    const st = { key: "task", dir: "asc", mech: "all", q: "" };
    const mechs = MECH_ORDER.filter((m) => members.some((mm) => mm.mechanism === m));
    const tableWrap = h("div", {});

    const cmp = (a, b) => {
      let av, bv;
      if (st.key === "task") { av = Number(a.task_id); bv = Number(b.task_id); if (Number.isNaN(av) || Number.isNaN(bv)) { av = String(a.task_id); bv = String(b.task_id); } }
      else if (st.key === "mechanism") { av = a.mechanism || ""; bv = b.mechanism || ""; }
      else { av = a[st.key]; bv = b[st.key]; }
      const d = av < bv ? -1 : av > bv ? 1 : 0;
      return st.dir === "asc" ? d : -d;
    };
    const setSort = (key) => { if (st.key === key) st.dir = st.dir === "asc" ? "desc" : "asc"; else { st.key = key; st.dir = "asc"; } render(); };
    const th = (key, label) =>
      h("th", { class: "sortable", onClick: () => setSort(key) }, label + (st.key === key ? (st.dir === "asc" ? " ▲" : " ▼") : ""));

    const toolbar = h(
      "div",
      { class: "form-row member-toolbar" },
      h("input", { class: "search", style: { maxWidth: "150px" }, placeholder: "filter task…", oninput: (e) => { st.q = e.target.value; render(); } }),
      h("select", { class: "select", onchange: (e) => { st.mech = e.target.value; render(); } },
        h("option", { value: "all" }, "all mechanisms"), ...mechs.map((m) => h("option", { value: m }, m))),
    );
    head.appendChild(toolbar);
    bodyS.appendChild(tableWrap);

    function render() {
      clear(tableWrap);
      let rows = members.slice();
      if (st.q) rows = rows.filter((m) => String(m.task_id).toLowerCase().includes(st.q.toLowerCase()));
      if (st.mech !== "all") rows = rows.filter((m) => m.mechanism === st.mech);
      rows.sort(cmp);

      const table = h("table", { class: "tbl" });
      table.appendChild(h("tr", {}, th("task", "task"), th("trial", "trial"), th("reward", "reward"), th("mechanism", "mechanism"), h("th", {}, "tool chain"), h("th", {}, "")));
      rows.forEach((mm) => {
        table.appendChild(
          h("tr", {},
            h("td", {}, mm.task_id),
            h("td", {}, mm.trial),
            h("td", {}, mm.reward.toFixed(2)),
            h("td", {}, mechanism(mm.mechanism)),
            h("td", { class: "mono tiny" }, (mm.tool_chain || []).join(" → ")),
            h("td", {}, h("button", { class: "btn small", onClick: () => navigate("/traces", { a: mm.simulation_id }) }, "open →")),
          ),
        );
      });
      tableWrap.appendChild(table);
      tableWrap.appendChild(h("div", { class: "muted tiny", style: { marginTop: "4px" } }, `${rows.length} of ${members.length} shown`));
      if (rows.length >= 2) {
        tableWrap.appendChild(
          h("button", { class: "btn", style: { marginTop: "8px" }, onClick: () => navigate("/traces", { a: rows[0].simulation_id, b: rows[1].simulation_id, diff: 1 }) }, "Diff first two shown →"),
        );
      }
    }
    render();
  }

  function clusterItem(c, totalFailures) {
    const share = (c.count / totalFailures) * 100;
    return h("div", { class: "clu-item", onClick: () => showCluster(c.id) },
      h("div", { class: "clu-top" }, h("span", { class: "cl-id" }, c.id), h("span", { class: "cl-count" }, `${c.count} · ${share.toFixed(0)}%`)),
      importanceBar(c.sims.map(memberMech), totalFailures, c.count),
      h("div", { class: "cl-summary-mini", title: c.summary || c.gloss || c.name }, c.summary || c.gloss || c.name),
    );
  }

  function buildList() {
    clear(list);
    const totalFailures = Math.max(1, clusters.reduce((a, c) => a + c.count, 0));
    list.appendChild(h("h3", {}, `Clusters (${clusters.length} · ${totalFailures} failures)`));
    clusters.forEach((c) => list.appendChild(clusterItem(c, totalFailures)));
  }

  buildList();
  wrap.appendChild(h("div", { class: "grid-cl" }, list, detail));

  const { params } = parseHash();
  showCluster(params.get("c") || (clusters[0] && clusters[0].id));
  return wrap;
}
