import { h } from "../dom.js";
import { contentNode } from "./jsontree.js";
import { alignSteps, kindLabel } from "./trace_util.js";

// Word-level LCS diff → two arrays of DOM nodes (<del>/<ins>/text).
function wordDiff(a, b) {
  a = a || "";
  b = b || "";
  const aw = a.split(/(\s+)/);
  const bw = b.split(/(\s+)/);
  const n = aw.length,
    m = bw.length;
  if (a === b || a.length > 4000 || b.length > 4000) {
    return [[document.createTextNode(a)], [document.createTextNode(b)]];
  }
  const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = aw[i] === bw[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const aout = [],
    bout = [];
  let i = 0,
    j = 0;
  const txt = (s) => document.createTextNode(s);
  const tag = (t, s) => h(t, {}, s);
  while (i < n && j < m) {
    if (aw[i] === bw[j]) {
      aout.push(txt(aw[i]));
      bout.push(txt(bw[j]));
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      aout.push(tag("del", aw[i++]));
    } else {
      bout.push(tag("ins", bw[j++]));
    }
  }
  while (i < n) aout.push(tag("del", aw[i++]));
  while (j < m) bout.push(tag("ins", bw[j++]));
  return [aout, bout];
}

function diffCell(step, side, other) {
  if (!step) return h("div", { class: "dcell " + side });
  const head = h(
    "div",
    { class: "shead" },
    `${kindLabel(step)} ${step.tool || ""} · #${step.i}`,
  );
  let body;
  if (step.kind === "turn") {
    if (other && step.content !== other.content) {
      const [aNodes, bNodes] = wordDiff(
        side === "a" ? step.content : other.content,
        side === "a" ? other.content : step.content,
      );
      body = h("pre", {}, ...(side === "a" ? aNodes : bNodes));
    } else {
      body = h("pre", {}, step.content || "");
    }
  } else {
    body = contentNode(step);
  }
  return h("div", { class: "dcell " + side }, head, body);
}

// Aligned, synchronized side-by-side diff. Equal runs collapse to a stub
// unless hideEqual is false; clicking the stub calls onShowEqual.
export function DiffView(simA, simB, hideEqual, onShowEqual) {
  const rows = alignSteps(simA.steps || [], simB.steps || []);
  const table = h("div", { class: "difftable" });
  let eq = [];
  const flush = () => {
    if (!eq.length) return;
    if (!hideEqual) {
      eq.forEach((r) =>
        table.appendChild(
          h("div", { class: "drow equal" }, diffCell(r.a, "a", r.b), diffCell(r.b, "b", r.a)),
        ),
      );
    } else {
      const n = eq.length;
      table.appendChild(
        h(
          "div",
          { class: "collapsed", onClick: () => onShowEqual && onShowEqual() },
          `⋯ ${n} unchanged step${n > 1 ? "s" : ""}`,
        ),
      );
    }
    eq = [];
  };
  for (const r of rows) {
    if (r.op === "equal") {
      eq.push(r);
      continue;
    }
    flush();
    table.appendChild(
      h("div", { class: "drow " + r.op }, diffCell(r.a, "a", r.b), diffCell(r.b, "b", r.a)),
    );
  }
  flush();
  return table;
}
