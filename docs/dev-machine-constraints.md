# Dev machine constraints (managed Databricks laptop)

This document describes how to set up and run software projects on a managed
Databricks corporate laptop. Copy it into new repos or link to it from your project README.

## Summary

| What you want | Use this | Do **not** use |
| --- | --- | --- |
| Python packages | **uv** + internal PyPI proxy | system `pip3` / `python3 -m pip` |
| Python runtime | **uv-managed CPython 3.12** in a project `.venv` | macOS system Python |
| Node.js | manually installed build under `~/.local/opt/` | Homebrew/system Node (not on PATH) |
| npm packages | **npm** + internal npm proxy | public `registry.npmjs.org` |
| Package installs | commands that need **full network** (proxies are allow-listed, not public) | assuming default registries resolve |

## Why the defaults break

### Public registries are blocked

Jamf enforces an `/etc/hosts` blocklist that **null-routes** public package
registries, including:

- `pypi.org` / `files.pythonhosted.org`
- `registry.npmjs.org`

`pip install` and `npm install` against the public internet will fail or hang.
You must use Databricks internal proxies instead.

### System Python cannot reach the internal proxy

macOS ships Python linked against **LibreSSL**, which cannot talk to the
internal PyPI proxy. Even if you point `pip` at the proxy URL, installs through
system `python3` / `pip3` are unreliable.

**Fix:** use [uv](https://docs.astral.sh/uv/), which bundles a modern TLS stack
and downloads its own CPython builds.

## One-time machine setup

Run these once per laptop (or after a wipe). They are not per-project.

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

Confirm: `uv --version`

Add to your shell profile (`~/.zshrc`):

```bash
export PATH="$HOME/.local/bin:$PATH"
export UV_INDEX_URL=https://pypi-proxy.dev.databricks.com/simple
```

`UV_INDEX_URL` tells uv (and `uv pip`) to use the internal PyPI mirror for all
projects on this machine.

### Install Node.js (manual tarball)

Node is **not** on the default PATH. Download an official build and extract it
under `~/.local/opt/`:

1. Download `node-v22.x-darwin-arm64.tar.gz` from
   [nodejs.org/dist/latest-v22.x/](https://nodejs.org/dist/latest-v22.x/)
2. Extract and place it, e.g.:

   ```bash
   mkdir -p ~/.local/opt
   tar -xzf node-v22.*-darwin-arm64.tar.gz -C ~/.local/opt
   ```

3. Add to `~/.zshrc` (adjust the version folder name to match what you extracted):

   ```bash
   export PATH="$HOME/.local/opt/node-v22.22.3-darwin-arm64/bin:$PATH"
   ```

Confirm: `node --version` and `npm --version`

### Point npm at the internal registry

```bash
npm config set registry https://npm-proxy.cloud.databricks.com/
npm config get registry   # should print the proxy URL
```

This writes to your user-level `~/.npmrc` and applies to all projects.

## Per-project setup

### Python backend

From your project root (adjust paths if your Python package lives elsewhere):

```bash
cd backend   # or wherever pyproject.toml / setup.py lives

export PATH="$HOME/.local/bin:$PATH"
export UV_INDEX_URL=https://pypi-proxy.dev.databricks.com/simple

# Create a venv with a modern CPython (3.12 recommended)
uv venv --python 3.12

source .venv/bin/activate
uv pip install -e ".[dev]"    # editable install + dev extras; needs network
```

**Day-to-day:**

```bash
cd backend
export PATH="$HOME/.local/bin:$PATH"
source .venv/bin/activate
pytest -q                      # or whatever your test runner is
```

**If `.venv` is missing:** run `uv venv --python 3.12` again, then reinstall.

**Dependency changes:** `uv pip install -e ".[dev]"` (or `uv pip install <pkg>`).

#### uv vs pip cheat sheet

| Task | Command |
| --- | --- |
| Create venv | `uv venv --python 3.12` |
| Activate venv | `source .venv/bin/activate` |
| Install project + dev deps | `uv pip install -e ".[dev]"` |
| Install a single package | `uv pip install requests` |
| Sync from a lock/requirements file | `uv pip install -r requirements.txt` |
| Run a tool without activating | `uv run pytest -q` |

Always set `UV_INDEX_URL` (or rely on it being in your shell profile) so uv
hits the internal proxy, not the blocked public PyPI.

### JavaScript / TypeScript frontend

```bash
cd frontend   # or wherever package.json lives

export PATH="$HOME/.local/opt/node-v22.22.3-darwin-arm64/bin:$PATH"
npm config get registry        # sanity check: internal proxy URL

npm install                    # needs network; only when deps change
npm run build                  # type-check + production build
npm run dev                    # local dev server (project-specific port)
```

Commit a `.nvmrc` or document the Node version in your README so teammates use
a compatible build. On this machine, the exact path under `~/.local/opt/` matters
more than nvm.

## Running both servers (full-stack projects)

Combine the PATH exports when you need Python and Node in one shell:

```bash
export PATH="$HOME/.local/opt/node-v22.22.3-darwin-arm64/bin:$HOME/.local/bin:$PATH"
```

Then start your backend and frontend however the project defines them (e.g.
`uvicorn` on `:8000`, Vite on `:5173`).

**Verify servers are up** (prefer this over assuming they crashed):

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
```

### Vite / Tailwind dev-server caveat

Vite does **not** reliably hot-reload changes to build/config files. After
editing `vite.config.ts`, `tailwind.config.js`, `postcss.config.*`,
`src/index.css`, or `package.json`, restart the dev server:

```bash
export PATH="$HOME/.local/opt/node-v22.22.3-darwin-arm64/bin:$PATH"
kill -9 "$(lsof -nP -iTCP:5173 -sTCP:LISTEN -t)" 2>/dev/null
cd frontend
rm -rf node_modules/.vite
npm run dev
```

Hard-refresh the browser (Cmd+Shift+R) after a restart to drop cached CSS.
Plain `.ts` / `.tsx` component edits hot-reload fine without a restart.

## Network and permissions

- **Installs and builds need network access.** The internal proxies are
  allow-listed; they are not the public internet, but tooling still needs
  outbound access to reach them.
- In Cursor's agent sandbox, `kill`, loopback `curl` to `localhost`, and some
  process management may be restricted. Use full permissions when stopping
  listeners or smoke-testing local servers.
- Background long-running dev servers; do not block an agent session waiting on
  them.

## New project checklist

Use this when bootstrapping a repo on this machine:

- [ ] `uv` installed and on PATH (`~/.local/bin`)
- [ ] `UV_INDEX_URL` set in shell profile
- [ ] Node 22.x extracted under `~/.local/opt/` and on PATH
- [ ] `npm config get registry` returns `https://npm-proxy.cloud.databricks.com/`
- [ ] Python: `uv venv --python 3.12` → `uv pip install -e ".[dev]"`
- [ ] Frontend: `npm install` → `npm run build`
- [ ] Document required PATH exports in the project README or a
      `.cursor/rules/dev-environment.mdc` for agents
- [ ] Tests pass: `pytest -q` (backend), `npm run build` (frontend)

## What to put in project docs

For each new repo, add a short **Setup** section that:

1. States this is a managed Databricks laptop (link to this doc or inline the
   proxy URLs).
2. Shows the exact `export PATH=...` lines for that project's layout.
3. Lists the create-venv / install / test commands.
4. Notes any project-specific ports, env vars, or auth (`databricks auth login`,
   API keys, etc.).

Example snippet for a README:

```bash
# Backend
cd backend
export PATH="$HOME/.local/bin:$PATH"
export UV_INDEX_URL=https://pypi-proxy.dev.databricks.com/simple
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q

# Frontend
cd ../frontend
export PATH="$HOME/.local/opt/node-v22.22.3-darwin-arm64/bin:$PATH"
npm install && npm run build
```

## Reference URLs

| Service | Internal proxy URL |
| --- | --- |
| PyPI (Python) | `https://pypi-proxy.dev.databricks.com/simple` |
| npm (JavaScript) | `https://npm-proxy.cloud.databricks.com/` |

## Common failures

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `pip` / `npm` timeout or "could not resolve host" | hitting blocked public registry | set `UV_INDEX_URL` or `npm config set registry` to internal proxy |
| SSL / TLS errors with system `pip3` | LibreSSL + system Python | use `uv` and a `uv`-managed venv |
| `command not found: node` | Node not on PATH | export `~/.local/opt/node-.../bin` |
| `command not found: uv` | uv not on PATH | export `~/.local/bin` |
| Stale / broken CSS in browser during dev | Vite cache after config change | restart dev server, clear `node_modules/.vite`, hard-refresh |
| Agent says server is down but you started it | sandbox blocks cross-shell localhost | check with `lsof`, run smoke tests with full permissions |

## Source

This guide is based on:

- `.cursor/rules/dev-environment.mdc` in the Tackle repo
- `README.md` → "Restricted/corporate network" section
- `.cursor/skills/launch-app/` and `.cursor/skills/verify-app/` environment notes
