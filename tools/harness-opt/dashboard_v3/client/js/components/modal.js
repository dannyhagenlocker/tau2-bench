// Lightweight tabbed modal (no framework). Tabs render lazily and are cached.
import { h, clear } from "../dom.js";

export function openModal({ title, subtitle, tabs, onClose }) {
  const overlay = h("div", { class: "modal-overlay" });
  const content = h("div", { class: "modal-content" });
  const tabbar = h("div", { class: "modal-tabs" });

  const rendered = new Map();
  const tabBtns = new Map();

  function close() {
    document.removeEventListener("keydown", onKey);
    overlay.remove();
    if (onClose) onClose();
  }
  function onKey(e) {
    if (e.key === "Escape") close();
  }

  function select(id) {
    for (const [tid, btn] of tabBtns) btn.classList.toggle("active", tid === id);
    clear(content);
    if (!rendered.has(id)) {
      const tab = tabs.find((t) => t.id === id);
      rendered.set(id, tab.render());
    }
    content.appendChild(rendered.get(id));
  }

  tabs.forEach((t) => {
    const btn = h("button", { class: "modal-tab", onClick: () => select(t.id) }, t.label);
    tabBtns.set(t.id, btn);
    tabbar.appendChild(btn);
  });

  const closeBtn = h("button", { class: "modal-close", onClick: close, title: "Close (Esc)" }, "✕");
  const modal = h(
    "div",
    { class: "modal" },
    h(
      "div",
      { class: "modal-head" },
      h("div", {}, h("h3", { class: "modal-title" }, title), subtitle ? h("div", { class: "muted tiny" }, subtitle) : null),
      closeBtn,
    ),
    tabbar,
    content,
  );

  overlay.appendChild(modal);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", onKey);
  document.body.appendChild(overlay);

  if (tabs.length) select(tabs[0].id);
  return { close, select };
}
