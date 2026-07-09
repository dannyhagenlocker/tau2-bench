import { clear, h } from "../dom.js";
import { store } from "../store.js";
import { navigate, parseHash } from "../router.js";
import { MECH_ORDER, badge, ftype, mechanism, mechanismColor } from "../components/widgets.js";

export function ClustersPage() {
  const s = store.summary;
  const wrap = h("div", { class: "page clusters" });
  const clusters = [...s.clusters].sort((a, b) => b.count - a.count);
  let mechFilter = "all";

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
        h("h3", {}, `${c.id} · ${c.label}`),
        h("span", {}, [mechanism(c.mechanism), ftype(c.failure_type)]),
      ),
    );
    if (c.gloss) head.appendChild(h("div", { class: "gloss" }, c.gloss));
    head.appendChild(h("div", { class: "sig mono tiny" }, c.signature || c.name));
    head.appendChild(h("div", { class: "muted tiny" }, `clustering method: ${c.method || "—"}`));
    if (c.blame && c.blame.length) head.appendChild(h("div", { class: "badges" }, ...c.blame.map((b) => badge(b))));

    const members = c.sims.map((sid) => s.sims[sid]).filter(Boolean);
    head.appendChild(h("div", { class: "muted small", style: { margin: "8px 0 0" } }, `${members.length} members · mechanism composition`));
    head.appendChild(mechComposition(c));

    const table = h("table", { class: "tbl" });
    table.appendChild(h("tr", {}, h("th", {}, "task"), h("th", {}, "trial"), h("th", {}, "reward"), h("th", {}, "mechanism"), h("th", {}, "tool chain"), h("th", {}, "")));
    members.forEach((mm) => {
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
    bodyS.appendChild(table);
    if (members.length >= 2) {
      bodyS.appendChild(
        h("button", { class: "btn", style: { marginTop: "10px" }, onClick: () => navigate("/traces", { a: members[0].simulation_id, b: members[1].simulation_id, diff: 1 }) }, "Diff first two members →"),
      );
    }
  }

  function clusterItem(c, maxCount) {
    return h("div", { class: "clu-item", onClick: () => showCluster(c.id) },
      h("div", { class: "clu-top" }, ftype(c.failure_type), h("span", { class: "cl-id" }, c.id), h("span", { class: "cl-count" }, c.count)),
      h("div", { class: "clu-barwrap" }, h("div", { class: "clu-bar", style: { width: (c.count / maxCount) * 100 + "%", background: mechanismColor(c.mechanism) } })),
      c.gloss ? h("div", { class: "cl-gloss" }, c.gloss) : null,
      h("div", { class: "cl-sig mono tiny", title: c.signature || c.name }, c.signature || c.name),
    );
  }

  function buildList() {
    clear(list);
    const present = [...new Set(clusters.map((c) => c.mechanism))];
    const sel = h("select", { class: "select", onchange: (e) => { mechFilter = e.target.value; buildList(); } },
      h("option", { value: "all", selected: mechFilter === "all" }, `all mechanisms (${clusters.length})`),
      ...MECH_ORDER.filter((m) => present.includes(m)).map((m) =>
        h("option", { value: m, selected: mechFilter === m }, `${m} (${clusters.filter((c) => c.mechanism === m).length})`)),
    );
    list.appendChild(h("div", { class: "panel-head" }, h("h3", {}, "Clusters by mechanism"), sel));

    const maxCount = Math.max(1, ...clusters.map((c) => c.count));
    const groups = MECH_ORDER
      .map((m) => [m, clusters.filter((c) => c.mechanism === m && (mechFilter === "all" || mechFilter === m))])
      .filter(([, cs]) => cs.length);
    groups.forEach(([m, cs]) => {
      list.appendChild(h("div", { class: "sec-title mech-head" }, mechanism(m), h("span", { class: "muted" }, ` ${cs.length}`)));
      cs.sort((a, b) => b.count - a.count).forEach((c) => list.appendChild(clusterItem(c, maxCount)));
    });
  }

  buildList();
  wrap.appendChild(h("div", { class: "grid-cl" }, list, detail));

  const { params } = parseHash();
  showCluster(params.get("c") || (clusters[0] && clusters[0].id));
  return wrap;
}
