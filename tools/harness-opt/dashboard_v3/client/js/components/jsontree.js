import { h } from "../dom.js";

// Collapsible JSON tree via native <details> (collapsed beyond depth 1).
export function jsonTree(value, depth = 0) {
  if (value === null) return h("span", { class: "j-null" }, "null");
  const t = typeof value;
  if (t === "number") return h("span", { class: "j-num" }, String(value));
  if (t === "boolean") return h("span", { class: "j-bool" }, String(value));
  if (t === "string") return h("span", { class: "j-str" }, JSON.stringify(value));

  const openAttr = depth < 1 ? { open: true } : {};
  if (Array.isArray(value)) {
    if (!value.length) return h("span", {}, "[]");
    const body = h(
      "div",
      { class: "j-body" },
      ...value.map((v) => h("div", { class: "j-row" }, jsonTree(v, depth + 1))),
    );
    return h("details", openAttr, h("summary", {}, `[ ] ${value.length} items`), body);
  }
  const keys = Object.keys(value);
  if (!keys.length) return h("span", {}, "{}");
  const body = h(
    "div",
    { class: "j-body" },
    ...keys.map((k) =>
      h("div", { class: "j-row" }, h("span", { class: "j-key" }, k), ": ", jsonTree(value[k], depth + 1)),
    ),
  );
  return h("details", openAttr, h("summary", {}, `{ } ${keys.length} keys`), body);
}

// Render a step's content: pretty JSON for tool payloads, else plain text.
export function contentNode(step) {
  const c = step.content || "";
  if (step.kind === "tool_call" || step.kind === "tool_result") {
    try {
      return h("div", { class: "json" }, jsonTree(JSON.parse(c), 0));
    } catch (e) {
      /* fall through to text */
    }
  }
  return h("pre", {}, c);
}
