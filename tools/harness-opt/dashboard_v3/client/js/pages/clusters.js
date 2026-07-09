import { h, clear } from "../dom.js";
import { store } from "../store.js";
import { navigate, parseHash } from "../router.js";
import { ftype, ftypeColor, badge } from "../components/widgets.js";

export function ClustersPage() {
  const s = store.summary;
  const wrap = h("div", { class: "page clusters" });
  const clusters = [...s.clusters].sort((a, b) => b.count - a.count);

  const detail = h("div", { class: "panel cluster-detail" });

  function showCluster(cid) {
    const c = clusters.find((x) => x.id === cid);
    clear(detail);
    if (!c) {
      detail.appendChild(h("div", { class: "muted" }, "Select a cluster."));
      return;
    }
    const head = h("div", { class: "cluster-detail-head" });
    const bodyS = h("div", { class: "cluster-detail-body" });
    detail.appendChild(head);
    detail.appendChild(bodyS);

    head.appendChild(
      h(
        "div",
        { class: "panel-head" },
        h("h3", {}, `${c.id} · ${c.label}`),
        ftype(c.failure_type),
      ),
    );
    if (c.gloss) head.appendChild(h("div", { class: "gloss" }, c.gloss));
    head.appendChild(h("div", { class: "sig mono tiny" }, c.signature || c.name));
    if (c.blame && c.blame.length)
      head.appendChild(h("div", { class: "badges" }, ...c.blame.map((b) => badge(b))));

    const members = c.sims.map((sid) => s.sims[sid]).filter(Boolean);
    head.appendChild(
      h("div", { class: "muted small", style: { margin: "8px 0 0" } }, `${members.length} members`),
    );
    const table = h("table", { class: "tbl" });
    table.appendChild(
      h(
        "tr",
        {},
        h("th", {}, "task"),
        h("th", {}, "trial"),
        h("th", {}, "reward"),
        h("th", {}, "tool chain"),
        h("th", {}, ""),
      ),
    );
    members.forEach((mm) => {
      table.appendChild(
        h(
          "tr",
          {},
          h("td", {}, mm.task_id),
          h("td", {}, mm.trial),
          h("td", {}, mm.reward.toFixed(2)),
          h("td", { class: "mono tiny" }, (mm.tool_chain || []).join(" → ")),
          h(
            "td",
            {},
            h(
              "button",
              {
                class: "btn small",
                onClick: () => navigate("/traces", { a: mm.simulation_id }),
              },
              "open →",
            ),
          ),
        ),
      );
    });
    bodyS.appendChild(table);

    if (members.length >= 2) {
      bodyS.appendChild(
        h(
          "button",
          {
            class: "btn",
            style: { marginTop: "10px" },
            onClick: () =>
              navigate("/traces", {
                a: members[0].simulation_id,
                b: members[1].simulation_id,
                diff: 1,
              }),
          },
          "Diff first two members →",
        ),
      );
    }
  }

  // cluster list (left)
  const list = h("div", { class: "panel cluster-list" });
  list.appendChild(h("h3", {}, `Clusters (${clusters.length})`));
  const maxCount = Math.max(1, ...clusters.map((c) => c.count));
  clusters.forEach((c) => {
    list.appendChild(
      h(
        "div",
        { class: "clu-item", onClick: () => showCluster(c.id) },
        h(
          "div",
          { class: "clu-top" },
          ftype(c.failure_type),
          h("span", { class: "cl-id" }, c.id),
          h("span", { class: "cl-count" }, c.count),
        ),
        h(
          "div",
          { class: "clu-barwrap" },
          h("div", {
            class: "clu-bar",
            style: {
              width: (c.count / maxCount) * 100 + "%",
              background: ftypeColor(c.failure_type),
            },
          }),
        ),
        c.gloss ? h("div", { class: "cl-gloss" }, c.gloss) : null,
        h("div", { class: "cl-sig mono tiny", title: c.signature || c.name }, c.signature || c.name),
      ),
    );
  });

  wrap.appendChild(h("div", { class: "grid-cl" }, list, detail));

  const { params } = parseHash();
  showCluster(params.get("c") || (clusters[0] && clusters[0].id));
  return wrap;
}
