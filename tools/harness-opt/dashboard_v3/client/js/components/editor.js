// Monaco diff-editor loader with a graceful <textarea> fallback (offline / CDN
// blocked). Monaco is loaded lazily from a CDN via its AMD loader so we don't
// vendor ~5MB into the repo.
import { h } from "../dom.js";

const MONACO_BASE = "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs";
let monacoPromise = null;

function loadMonaco() {
  if (monacoPromise) return monacoPromise;
  monacoPromise = new Promise((resolve, reject) => {
    if (window.monaco) return resolve(window.monaco);
    const loader = document.createElement("script");
    loader.src = MONACO_BASE + "/loader.js";
    loader.onload = () => {
      try {
        window.require.config({ paths: { vs: MONACO_BASE } });
        window.require(["vs/editor/editor.main"], () => resolve(window.monaco));
      } catch (e) {
        reject(e);
      }
    };
    loader.onerror = () => reject(new Error("failed to load Monaco from CDN"));
    document.head.appendChild(loader);
  });
  return monacoPromise;
}

// Returns { node, getModified(), dispose() }. node is ready to append; the
// editor mounts asynchronously once Monaco is available.
export function diffEditor(original, modified, { language = "python" } = {}) {
  const host = h("div", { class: "monaco-host" });
  const state = { getModified: () => modified, dispose: () => {} };

  loadMonaco()
    .then((monaco) => {
      const ed = monaco.editor.createDiffEditor(host, {
        automaticLayout: true,
        renderSideBySide: true,
        originalEditable: false,
        readOnly: false,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 12,
      });
      const om = monaco.editor.createModel(original, language);
      const mm = monaco.editor.createModel(modified, language);
      ed.setModel({ original: om, modified: mm });
      state.getModified = () => mm.getValue();
      state.dispose = () => {
        ed.dispose();
        om.dispose();
        mm.dispose();
      };
    })
    .catch(() => {
      // Fallback: editable textarea for the modified side.
      const ta = h("textarea", { class: "editor-fallback", spellcheck: "false" });
      ta.value = modified;
      host.appendChild(h("div", { class: "muted tiny" }, "Monaco unavailable — plain editor:"));
      host.appendChild(ta);
      state.getModified = () => ta.value;
    });

  return { node: host, getModified: () => state.getModified(), dispose: () => state.dispose() };
}
