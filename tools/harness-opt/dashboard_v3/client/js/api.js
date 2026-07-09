// Thin fetch wrappers + a per-simulation cache (traces are lazy-loaded).

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

const enc = encodeURIComponent;

export const api = {
  runs: () => getJSON("/api/runs"),
  summary: (run) => getJSON(`/api/runs/${enc(run)}/summary`),
  tasks: (run) => getJSON(`/api/runs/${enc(run)}/tasks`),
  summaryMd: (run) => getJSON(`/api/runs/${enc(run)}/summary_md`),
  sim: (run, sid) => getJSON(`/api/runs/${enc(run)}/sims/${enc(sid)}`),
};

const simCache = new Map();

export async function getSim(run, sid) {
  const key = `${run}|${sid}`;
  if (!simCache.has(key)) simCache.set(key, await api.sim(run, sid));
  return simCache.get(key);
}
