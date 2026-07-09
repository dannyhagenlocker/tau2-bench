import { h } from "../dom.js";

// Failure-mode palette (mirrors .ftype.* in styles.css): DB=blue, NL=amber,
// mixed=red, pass=green, communicate=violet, termination=slate.
const FTYPE_COLOR = {
  pass: "#16a34a",
  db_only: "#2563eb",
  nl_only: "#d97706",
  mixed: "#dc2626",
  communicate_only: "#7c3aed",
  termination: "#64748b",
};

export function ftypeColor(t) {
  return FTYPE_COLOR[t] || "#64748b";
}

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
