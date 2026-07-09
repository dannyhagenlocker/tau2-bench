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

// Primary axis: deterministic root-cause mechanism. Ordered roughly
// most→least actionable; colors are saturated (for bars/plots), pills are
// outlined/light (see .mech.* in styles.css).
const MECH_COLOR = {
  bailed_transfer: "#dc2626",
  stalled_no_action: "#ea580c",
  wrong_params: "#d97706",
  incomplete_multitask: "#7c3aed",
  identification_failure: "#0891b2",
  comm_miss: "#2563eb",
  premature_termination: "#64748b",
  other: "#9ca3af",
  pass: "#16a34a",
  unknown: "#9ca3af",
};
export const MECH_ORDER = [
  "bailed_transfer",
  "stalled_no_action",
  "wrong_params",
  "incomplete_multitask",
  "identification_failure",
  "comm_miss",
  "premature_termination",
  "other",
  "pass",
];
const MECH_TIP = {
  bailed_transfer: "escalated to a human without completing the task",
  stalled_no_action: "never executed the required write (didn't even bail)",
  wrong_params: "performed the write but with wrong values/operation",
  incomplete_multitask: "did some required writes, missed others",
  identification_failure: "couldn't find the user/order, so couldn't proceed",
  comm_miss: "DB correct, but didn't tell the user required info",
  premature_termination: "ended abnormally (max steps / too many errors)",
  other: "unclassified",
  pass: "non-failure",
};

export function mechanismColor(m) {
  return MECH_COLOR[m] || "#9ca3af";
}

export function mechanism(code) {
  const m = code || "other";
  return h("span", { class: "mech " + m, title: MECH_TIP[m] || m }, m);
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
