import { h } from "../dom.js";
import { contentNode } from "./jsontree.js";
import { kbadgeClass, kindLabel, nodeColor, parents } from "./trace_util.js";

// Stateful waterfall: indented node tree with timing bars, subtree collapse
// (caret), and per-node detail expansion (click label). Re-renders into itself.
export function Waterfall(sim) {
  const nodes = sim.steps || [];
  const total = Math.max(sim.total_dur || 0, 0.001);
  const pid = parents(nodes);
  const hasKids = nodes.map((_, i) => pid.includes(i));
  const collapsed = new Set();
  const open = new Set();
  const root = h("div", { class: "wf" });

  function hidden(i) {
    let p = pid[i];
    while (p !== -1) {
      if (collapsed.has(p)) return true;
      p = pid[p];
    }
    return false;
  }

  function render() {
    root.replaceChildren();
    nodes.forEach((n, i) => {
      if (hidden(i)) return;
      const caret = hasKids[i]
        ? h(
            "span",
            {
              class: "caret",
              onClick: () => {
                collapsed.has(i) ? collapsed.delete(i) : collapsed.add(i);
                render();
              },
            },
            collapsed.has(i) ? "▸" : "▾",
          )
        : h("span", { class: "caret-empty" });

      const barFill = h("span", {
        class: "bar",
        style: {
          left: (n.start / total) * 100 + "%",
          width: Math.max((n.dur / total) * 100, 0.6) + "%",
          background: nodeColor(n),
        },
      });

      const row = h(
        "div",
        {
          class: `wfrow ${n.kind} ${n.error ? "err" : ""}`,
          style: { paddingLeft: 8 + n.depth * 16 + "px" },
        },
        caret,
        h("span", { class: "kbadge " + kbadgeClass(n) }, kindLabel(n)),
        h(
          "span",
          {
            class: "wlabel",
            title: n.label,
            onClick: () => {
              open.has(i) ? open.delete(i) : open.add(i);
              render();
            },
          },
          n.label || "",
        ),
        h("span", { class: "track" }, barFill),
        h("span", { class: "dur" }, n.dur >= 0.01 ? n.dur.toFixed(2) + "s" : ""),
        h("span", { class: "cost" }, n.cost ? "$" + n.cost.toFixed(4) : ""),
      );
      root.appendChild(row);
      if (open.has(i)) {
        root.appendChild(
          h(
            "div",
            { class: "wdetail", style: { marginLeft: 8 + n.depth * 16 + 20 + "px" } },
            contentNode(n),
          ),
        );
      }
    });
  }

  render();
  return root;
}
