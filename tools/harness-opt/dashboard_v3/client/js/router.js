// Minimal hash router: #/path?query

export function parseHash() {
  const raw = location.hash.slice(1) || "/overview";
  const [path, qs] = raw.split("?");
  return { path, params: new URLSearchParams(qs || "") };
}

export function navigate(path, params) {
  let hash = "#" + path;
  if (params) {
    const s = new URLSearchParams(params).toString();
    if (s) hash += "?" + s;
  }
  if (location.hash === hash) window.dispatchEvent(new Event("hashchange"));
  else location.hash = hash;
}

export function onRoute(fn) {
  window.addEventListener("hashchange", fn);
}
