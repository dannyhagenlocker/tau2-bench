import { h, mount, clear } from "./dom.js";
import { store, loadRuns, selectRun, ensureSummary } from "./store.js";
import { parseHash, navigate, onRoute } from "./router.js";
import { spinner } from "./components/widgets.js";
import { OverviewPage } from "./pages/overview.js";
import { ClustersPage } from "./pages/clusters.js";
import { TracesPage } from "./pages/traces.js";
import { ComparePage } from "./pages/compare.js";
import { EmbeddingPage } from "./pages/embedding.js";
import { ProposalsPage } from "./pages/proposals.js";

const NAV = [
  ["/overview", "Overview"],
  ["/clusters", "Clusters"],
  ["/embedding", "Embedding"],
  ["/traces", "Traces"],
  ["/compare", "Compare runs"],
  ["/proposals", "Proposals"],
];
const PAGES = {
  "/overview": OverviewPage,
  "/clusters": ClustersPage,
  "/embedding": EmbeddingPage,
  "/traces": TracesPage,
  "/compare": ComparePage,
  "/proposals": ProposalsPage,
};

const root = document.getElementById("app");
let contentEl, navEl, runSelect;

function shell() {
  const runOptions = store.runs.map((r) =>
    h("option", { value: r.run, selected: r.run === store.run }, r.run),
  );
  runSelect = h(
    "select",
    {
      class: "run-select",
      onchange: async (e) => {
        await selectRun(e.target.value);
        shell(); // rebuild topbar meta for the new run
        route();
      },
    },
    ...runOptions,
  );

  navEl = h("nav", { class: "nav" });
  contentEl = h("div", { class: "content" });

  const m = store.summary ? store.summary.manifest : {};
  const header = h(
    "header",
    { class: "topbar" },
    h("div", { class: "brand" }, "harness-opt"),
    h("div", { class: "run-pick" }, h("label", {}, "run"), runSelect),
    h(
      "div",
      { class: "topmeta" },
      store.summary
        ? `${m.domain} · ${m.num_simulations} sims · pass ${(store.summary.pass_rate * 100).toFixed(1)}% · agent ${m.agent_llm || "—"}`
        : "",
    ),
  );

  mount(root, h("div", { class: "app" }, header, h("div", { class: "body" }, h("aside", { class: "side" }, navEl), contentEl)));
  renderNav();
}

function renderNav() {
  const { path } = parseHash();
  clear(navEl);
  NAV.forEach(([p, label]) => {
    navEl.appendChild(
      h(
        "a",
        { class: "navlink " + (p === path ? "active" : ""), href: "#" + p },
        label,
      ),
    );
  });
}

async function route() {
  renderNav();
  const { path } = parseHash();
  const Page = PAGES[path] || OverviewPage;
  clear(contentEl);
  contentEl.appendChild(spinner());
  try {
    await ensureSummary();
    clear(contentEl);
    contentEl.appendChild(Page());
  } catch (e) {
    clear(contentEl);
    contentEl.appendChild(h("div", { class: "error" }, "Error: " + e.message));
  }
}

async function boot() {
  mount(root, spinner("Loading runs…"));
  try {
    await loadRuns();
    if (!store.run) {
      mount(root, h("div", { class: "empty" }, "No analyzed runs found. Run: uv run python tools/harness-opt/cli.py analyze --run <name> --mock-label"));
      return;
    }
    await ensureSummary();
    if (!location.hash) location.hash = "#/overview";
    shell();
    onRoute(route);
    route();
  } catch (e) {
    mount(root, h("div", { class: "error" }, "Failed to start: " + e.message));
  }
}

boot();
