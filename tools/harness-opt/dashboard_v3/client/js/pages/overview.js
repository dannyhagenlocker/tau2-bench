import { h } from "../dom.js";
import { store } from "../store.js";
import { navigate } from "../router.js";
import { card, mechanism, mechanismColor, bar } from "../components/widgets.js";

export function OverviewPage() {
  const s = store.summary;
  const m = s.manifest;
  const wrap = h("div", { class: "page" });

  wrap.appendChild(
    h(
      "div",
      { class: "cards" },
      card(m.num_simulations, "simulations"),
      card((s.pass_rate * 100).toFixed(1) + "%", "pass rate"),
      card(s.n_failures, "failures"),
      card(m.num_trials ?? "—", "trials"),
      card(s.n_clusters, "clusters", `${s.n_singletons} singletons`),
      card(m.agent_llm || "—", "agent LLM"),
    ),
  );

  // L0 = root-cause mechanism breakdown (biggest insight), normalized by
  // total traces so each bar reads as a share of all sims.
  const totalSims = Math.max(1, s.l0.reduce((a, c) => a + c.count, 0));
  const l0 = h(
    "div",
    { class: "panel" },
    h("h3", {}, "Root cause (mechanism)"),
    ...s.l0.map((c) => {
      const code = c.name.split(":")[0];
      const pct = (c.count / totalSims) * 100;
      return h(
        "div",
        { class: "l0line" },
        h("span", { class: "l0name" }, mechanism(code)),
        h("span", { class: "l0bar" }, bar(c.count / totalSims, mechanismColor(code), mechanismColor(code) + "22")),
        h("span", { class: "l0cnt" }, `${c.count} · ${pct.toFixed(0)}%`),
      );
    }),
  );

  // Top clusters preview
  const top = [...s.clusters].sort((a, b) => b.count - a.count).slice(0, 8);
  const clusters = h(
    "div",
    { class: "panel" },
    h(
      "div",
      { class: "panel-head" },
      h("h3", {}, "Top failure clusters"),
      h("button", { class: "btn small", onClick: () => navigate("/clusters") }, "View all →"),
    ),
    ...top.map((c) =>
      h(
        "div",
        {
          class: "clusterline",
          onClick: () => navigate("/clusters", { c: c.id }),
        },
        mechanism(c.mechanism),
        h("span", { class: "cl-id" }, c.id),
        h("span", { class: "cl-count" }, "n=" + c.count),
        h("span", { class: "cl-sig", title: c.signature || c.name }, c.gloss || c.signature || c.name),
      ),
    ),
  );

  wrap.appendChild(h("div", { class: "grid2" }, l0, clusters));
  return wrap;
}
