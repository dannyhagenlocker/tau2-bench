"""Pluggable coding-agent backends that edit the harness inside a worktree.

A proposal's harness change is produced by a coder backend run in the lineage
worktree. Backends:

- ``openai``  — **default, self-contained.** Uses the provided OpenAI key via
  ``tau2.utils.llm_utils.generate`` to produce structured search/replace edits,
  applied by us against a precise allowlist (``lib/allowlist.py``). Cost counts
  toward the project's single $50 budget and is captured in ``coder_log.json``.
- ``claude``  — Claude Code CLI; OPTIONAL / off-ledger (external subscription).
- ``cursor``  — Cursor CLI or ``cursor-sdk``; OPTIONAL / off-ledger.
- ``manual``  — no auto-edit; prep the worktree + evidence and stop. Test default.

Only the ``openai`` backend is self-contained and reproducible from just the API
key, so it is the default; ``claude``/``cursor`` are opt-in dev conveniences and
should be reported as a tooling model-difference if used.

Every run is captured verbatim into ``coder_log.json`` so the artifact package
records *what was proposed and what happened*.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_TIMEOUT_S = 1800
DEFAULT_PROPOSER_MODEL = "gpt-4.1"  # cheap dev model; eval always runs on gpt-5.5
_ALLOWED_TOOLS = "Edit Write Read Bash(git *)"


@dataclass
class CoderResult:
    backend: str
    ok: bool
    summary: str = ""
    session_id: Optional[str] = None
    error: Optional[str] = None
    cmd: list[str] = field(default_factory=list)
    returncode: Optional[int] = None
    raw_stdout: str = ""
    raw_stderr: str = ""
    model: Optional[str] = None
    cost: Optional[float] = None
    edited_paths: list[str] = field(default_factory=list)

    def to_log(self, prompt: str) -> dict:
        return {
            "backend": self.backend,
            "ok": self.ok,
            "summary": self.summary,
            "session_id": self.session_id,
            "error": self.error,
            "model": self.model,
            "cost": self.cost,
            "edited_paths": self.edited_paths,
            "cmd": self.cmd,
            "returncode": self.returncode,
            "prompt": prompt,
            "stdout": self.raw_stdout[-20000:],
            "stderr": self.raw_stderr[-8000:],
        }


class CoderBackend:
    name: str = "base"

    def available(self) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def run(self, prompt: str, cwd: Path) -> CoderResult:  # pragma: no cover
        raise NotImplementedError


_OUTPUT_SPEC = """\
## Output format
Respond with ONLY a single JSON object (no prose, no markdown fences):
{
  "hypothesis": "why this failure mode happens",
  "risk": "what could regress",
  "summary": "one-line description of the change",
  "edits": [
    {"path": "src/tau2/agent/llm_agent.py",
     "old_string": "<exact, UNIQUE existing snippet>",
     "new_string": "<replacement>"},
    {"path": "src/tau2/agent/my_agent.py", "new_file": true, "content": "<full file>"}
  ]
}
Rules:
- `old_string` MUST be an EXACT, UNIQUE substring of the current file shown below.
- Make the SMALLEST change that addresses the one failure mode; prefer editing
  src/tau2/agent/llm_agent.py.
- Only use paths from the allowlist above.
"""


def _extract_json(content: str) -> Optional[dict]:
    content = (content or "").strip()
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return None


def _apply_edits(cwd: Path, edits: list[dict]) -> tuple[bool, Optional[str], list[str]]:
    """Validate ALL edits, then apply atomically. Returns (ok, error, edited_paths)."""
    from lib.allowlist import normalize

    root = cwd.resolve()
    planned: list[tuple[str, Path, object]] = []
    touched: list[str] = []
    for e in edits:
        rel = normalize(e.get("path", ""))
        target = (cwd / rel).resolve()
        if not (target == root or str(target).startswith(str(root) + os.sep)):
            return False, f"path escapes worktree: {rel}", []
        if e.get("new_file"):
            content = e.get("content")
            if content is None:
                return False, f"new_file edit missing 'content': {rel}", []
            planned.append(("write", target, content))
        else:
            old, new = e.get("old_string"), e.get("new_string")
            if old is None or new is None:
                return False, f"edit missing old_string/new_string: {rel}", []
            if not target.exists():
                return False, f"target file does not exist: {rel}", []
            text = target.read_text()
            n = text.count(old)
            if n == 0:
                return False, f"old_string not found in {rel}", []
            if n > 1:
                return False, f"old_string not unique in {rel} ({n} matches)", []
            planned.append(("replace", target, (text, old, new)))
        touched.append(rel)

    for kind, target, payload in planned:
        if kind == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload)  # type: ignore[arg-type]
        else:
            text, old, new = payload  # type: ignore[misc]
            target.write_text(text.replace(old, new, 1))
    return True, None, touched


class OpenAICoder(CoderBackend):
    """Self-contained proposer: OpenAI-key LLM emits structured, allowlisted edits."""

    name = "openai"

    def __init__(self, model: str = DEFAULT_PROPOSER_MODEL):
        self._model = model

    def available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def run(self, prompt: str, cwd: Path) -> CoderResult:
        from lib.allowlist import ALLOWED_FILES, allowlist_for_prompt, assert_allowed

        file_blocks = []
        for rel in sorted(ALLOWED_FILES):
            fp = cwd / rel
            if fp.exists():
                file_blocks.append(f"### FILE: {rel}\n```python\n{fp.read_text()}\n```")
        full_prompt = "\n\n".join(
            [
                prompt,
                allowlist_for_prompt(),
                "## Current contents of editable files\n" + "\n\n".join(file_blocks),
                _OUTPUT_SPEC,
            ]
        )

        try:
            from tau2.data_model.message import UserMessage
            from tau2.utils.llm_utils import generate

            resp = generate(
                model=self._model,
                messages=[UserMessage(role="user", content=full_prompt)],
                call_name="harness_proposal",
                temperature=0,
            )
        except Exception as exc:  # noqa: BLE001 - surface as startup failure
            return CoderResult(
                backend=self.name,
                ok=False,
                error=f"generate failed: {exc}",
                model=self._model,
            )

        content = resp.content or ""
        cost = getattr(resp, "cost", None)
        data = _extract_json(content)
        if data is None:
            return CoderResult(
                backend=self.name,
                ok=False,
                error="could not parse JSON edits from model output",
                model=self._model,
                cost=cost,
                raw_stdout=content,
            )
        edits = data.get("edits") or []
        summary = data.get("summary") or data.get("hypothesis") or ""
        if not edits:
            return CoderResult(
                backend=self.name,
                ok=False,
                error="model returned no edits",
                summary=summary,
                model=self._model,
                cost=cost,
                raw_stdout=content,
            )
        try:
            assert_allowed([e.get("path", "") for e in edits])
        except PermissionError as exc:
            return CoderResult(
                backend=self.name,
                ok=False,
                error=str(exc),
                summary=summary,
                model=self._model,
                cost=cost,
                raw_stdout=content,
            )
        ok, err, touched = _apply_edits(cwd, edits)
        return CoderResult(
            backend=self.name,
            ok=ok,
            summary=summary,
            error=err,
            model=self._model,
            cost=cost,
            edited_paths=touched,
            raw_stdout=content,
        )


class ManualCoder(CoderBackend):
    name = "manual"

    def available(self) -> bool:
        return True

    def run(self, prompt: str, cwd: Path) -> CoderResult:
        return CoderResult(
            backend=self.name,
            ok=True,
            summary=(
                "manual backend: no automated edit performed. Apply the harness "
                "change by hand in the worktree, then re-run with --eval or accept."
            ),
        )


class ClaudeCoder(CoderBackend):
    name = "claude"

    def __init__(
        self, binary: Optional[str] = None, timeout_s: int = DEFAULT_TIMEOUT_S
    ):
        self._binary = (
            binary
            or shutil.which("claude")
            or str(Path.home() / ".local" / "bin" / "claude")
        )
        self._timeout_s = timeout_s

    def available(self) -> bool:
        return bool(self._binary) and Path(self._binary).exists()

    def run(self, prompt: str, cwd: Path) -> CoderResult:
        cmd = [
            self._binary,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--allowed-tools",
            _ALLOWED_TOOLS,
            "--add-dir",
            str(cwd),
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return CoderResult(
                backend=self.name,
                ok=False,
                error=f"timeout after {self._timeout_s}s",
                cmd=cmd,
                raw_stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                raw_stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
            )

        summary, session_id, is_error = _parse_claude_json(proc.stdout)
        ok = proc.returncode == 0 and not is_error
        return CoderResult(
            backend=self.name,
            ok=ok,
            summary=summary,
            session_id=session_id,
            error=None if ok else f"claude returned code {proc.returncode}",
            cmd=cmd,
            returncode=proc.returncode,
            raw_stdout=proc.stdout,
            raw_stderr=proc.stderr,
        )


def _parse_claude_json(stdout: str) -> tuple[str, Optional[str], bool]:
    """Extract (result_text, session_id, is_error) from `claude -p --output-format json`."""
    stdout = (stdout or "").strip()
    if not stdout:
        return "", None, True
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        # Fall back to raw text (older/newer CLI formats).
        return stdout[:4000], None, False
    if isinstance(data, list):  # streamed array of messages
        data = data[-1] if data else {}
    summary = data.get("result") or data.get("text") or ""
    session_id = data.get("session_id") or data.get("sessionId")
    is_error = bool(data.get("is_error") or data.get("subtype") == "error")
    return str(summary)[:4000], session_id, is_error


class CursorCoder(CoderBackend):
    name = "cursor"

    def __init__(self, timeout_s: int = DEFAULT_TIMEOUT_S):
        self._binary = shutil.which("cursor-agent")
        self._timeout_s = timeout_s

    def available(self) -> bool:
        if self._binary:
            return True
        try:  # optional Python SDK
            import cursor_sdk  # noqa: F401

            return bool(os.environ.get("CURSOR_API_KEY"))
        except ImportError:
            return False

    def run(self, prompt: str, cwd: Path) -> CoderResult:
        if self._binary:
            cmd = [self._binary, "-p", prompt, "--output-format", "json"]
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_s,
                )
            except subprocess.TimeoutExpired:
                return CoderResult(
                    backend=self.name, ok=False, error="timeout", cmd=cmd
                )
            ok = proc.returncode == 0
            return CoderResult(
                backend=self.name,
                ok=ok,
                summary=proc.stdout[:4000],
                cmd=cmd,
                returncode=proc.returncode,
                raw_stdout=proc.stdout,
                raw_stderr=proc.stderr,
                error=None if ok else f"cursor-agent code {proc.returncode}",
            )
        return self._run_sdk(prompt, cwd)

    def _run_sdk(self, prompt: str, cwd: Path) -> CoderResult:
        try:
            from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
        except ImportError:
            return CoderResult(
                backend=self.name,
                ok=False,
                error="cursor backend unavailable: install cursor-sdk or cursor-agent",
            )
        try:
            result = Agent.prompt(
                prompt,
                AgentOptions(
                    api_key=os.environ.get("CURSOR_API_KEY"),
                    model="composer-2.5",
                    local=LocalAgentOptions(cwd=str(cwd)),
                ),
            )
        except Exception as exc:  # noqa: BLE001 - surface as run failure
            return CoderResult(backend=self.name, ok=False, error=str(exc))
        ok = getattr(result, "status", "error") != "error"
        return CoderResult(
            backend=self.name,
            ok=ok,
            summary=str(getattr(result, "result", ""))[:4000],
            session_id=getattr(result, "id", None),
            error=None if ok else "cursor sdk run status=error",
        )


_BACKENDS: dict[str, type[CoderBackend]] = {
    "openai": OpenAICoder,
    "claude": ClaudeCoder,
    "cursor": CursorCoder,
    "manual": ManualCoder,
}


def get_coder(name: str = "auto", *, model: Optional[str] = None) -> CoderBackend:
    """Resolve a coder backend.

    'auto' prefers the self-contained OpenAI proposer (uses the project's OpenAI
    key), then the optional off-ledger CLIs, else manual.
    """
    if name != "auto":
        if name not in _BACKENDS:
            raise ValueError(
                f"Unknown coder backend: {name}. Choices: {sorted(_BACKENDS) + ['auto']}"
            )
        if name == "openai":
            return OpenAICoder(model=model or DEFAULT_PROPOSER_MODEL)
        return _BACKENDS[name]()
    openai_backend = OpenAICoder(model=model or DEFAULT_PROPOSER_MODEL)
    if openai_backend.available():
        return openai_backend
    for candidate in ("claude", "cursor"):
        backend = _BACKENDS[candidate]()
        if backend.available():
            return backend
    return ManualCoder()
