// Global app state: run list + selected run + its summary (cached).

import { api } from "./api.js";

export const store = {
  runs: [],
  run: null,
  summary: null,
};

const LS_KEY = "harness_opt_run";

export async function loadRuns() {
  store.runs = await api.runs();
  const saved = localStorage.getItem(LS_KEY);
  const names = store.runs.map((r) => r.run);
  store.run = names.includes(saved) ? saved : names[0] || null;
  return store.runs;
}

export async function selectRun(run) {
  store.run = run;
  localStorage.setItem(LS_KEY, run);
  store.summary = null;
  return ensureSummary();
}

export async function ensureSummary() {
  if (!store.run) return null;
  if (!store.summary || store.summary.run !== store.run) {
    store.summary = await api.summary(store.run);
  }
  return store.summary;
}
