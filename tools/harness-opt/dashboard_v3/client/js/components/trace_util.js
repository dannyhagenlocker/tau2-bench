// Shared helpers over the node/step model used by waterfall + diff.

export function nodeColor(n) {
  if (n.error) return "#dc2626";
  if (n.kind === "tool_call") return "#7c3aed";
  if (n.kind === "tool_result") return "#16a34a";
  if (n.lane === "user") return "#2563eb";
  if (n.lane === "assistant") return "#0d9488";
  return "#9ca3af";
}

export function kindLabel(n) {
  if (n.kind === "tool_call") return "call";
  if (n.kind === "tool_result") return "result";
  return n.lane;
}

export function kbadgeClass(n) {
  if (n.kind === "tool_call") return "call";
  if (n.kind === "tool_result") return "tool";
  return n.lane;
}

// parent index for each node (nearest previous node of smaller depth)
export function parents(nodes) {
  const pid = new Array(nodes.length).fill(-1);
  const stack = [];
  nodes.forEach((n, i) => {
    while (stack.length && nodes[stack[stack.length - 1]].depth >= n.depth) stack.pop();
    pid[i] = stack.length ? stack[stack.length - 1] : -1;
    stack.push(i);
  });
  return pid;
}

// LCS alignment over value-free step keys, with adjacent add/remove paired
// into "replace" rows for a tidy side-by-side.
export function alignSteps(A, B) {
  const n = A.length,
    m = B.length;
  const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = A[i].key === B[j].key ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const raw = [];
  let i = 0,
    j = 0;
  while (i < n && j < m) {
    if (A[i].key === B[j].key) {
      raw.push({ a: A[i], b: B[j], op: "equal" });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      raw.push({ a: A[i], b: null, op: "remove" });
      i++;
    } else {
      raw.push({ a: null, b: B[j], op: "add" });
      j++;
    }
  }
  while (i < n) raw.push({ a: A[i++], b: null, op: "remove" });
  while (j < m) raw.push({ a: null, b: B[j++], op: "add" });

  const out = [];
  let k = 0;
  while (k < raw.length) {
    if (raw[k].op === "equal") {
      out.push(raw[k]);
      k++;
      continue;
    }
    const rem = [],
      add = [];
    while (k < raw.length && raw[k].op !== "equal") {
      (raw[k].op === "remove" ? rem : add).push(raw[k]);
      k++;
    }
    for (let t = 0; t < Math.max(rem.length, add.length); t++) {
      const a = rem[t] ? rem[t].a : null;
      const b = add[t] ? add[t].b : null;
      out.push({ a, b, op: a && b ? "replace" : a ? "remove" : "add" });
    }
  }
  return out;
}
