// Thin fetch wrappers + a per-simulation cache (traces are lazy-loaded).

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

const enc = encodeURIComponent;

export const api = {
  runs: () => getJSON("/api/runs"),
  summary: (run) => getJSON(`/api/runs/${enc(run)}/summary`),
  tasks: (run) => getJSON(`/api/runs/${enc(run)}/tasks`),
  embedding: (run) => getJSON(`/api/runs/${enc(run)}/embedding`),
  summaryMd: (run) => getJSON(`/api/runs/${enc(run)}/summary_md`),
  sim: (run, sid) => getJSON(`/api/runs/${enc(run)}/sims/${enc(sid)}`),
  // Phase 2 proposals
  lineages: () => getJSON("/api/lineages"),
  proposals: (run) => getJSON(`/api/runs/${enc(run)}/proposals`),
  proposal: (run, pid) => getJSON(`/api/runs/${enc(run)}/proposals/${enc(pid)}`),
  propose: (run, body) => postJSON(`/api/runs/${enc(run)}/propose`, body),
  accept: (run, pid) => postJSON(`/api/runs/${enc(run)}/proposals/${enc(pid)}/accept`),
  reject: (run, pid) => postJSON(`/api/runs/${enc(run)}/proposals/${enc(pid)}/reject`),
};

const simCache = new Map();

export async function getSim(run, sid) {
  const key = `${run}|${sid}`;
  if (!simCache.has(key)) simCache.set(key, await api.sim(run, sid));
  return simCache.get(key);
}
