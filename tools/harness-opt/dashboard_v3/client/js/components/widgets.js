import { h } from "../dom.js";

export function ftype(t) {
  return h("span", { class: "ftype " + t }, t);
}

export function badge(text, cls) {
  return h("span", { class: "badge " + (cls || "") }, text);
}

export function card(value, label, sub) {
  return h(
    "div",
    { class: "card" },
    h("div", { class: "card-v" }, value),
    h("div", { class: "card-l" }, label),
    sub ? h("div", { class: "card-s" }, sub) : null,
  );
}

export function spinner(text) {
  return h("div", { class: "spinner" }, text || "Loading…");
}

export function bar(fraction, color) {
  const pct = Math.max(0, Math.min(1, fraction)) * 100;
  return h(
    "div",
    { class: "hbar" },
    h("div", { class: "hbar-fill", style: { width: pct + "%", background: color || "#2563eb" } }),
  );
}

export function fmtDur(s) {
  if (s == null) return "";
  return s >= 0.01 ? s.toFixed(2) + "s" : "";
}
