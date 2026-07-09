"""Pluggable coding-agent backends that edit the harness inside a worktree.

A proposal's actual harness change is produced by a local coding-agent CLI run
headless in the lineage worktree. Backends:

- ``claude``  — Claude Code CLI (`claude -p ... --output-format json`); installed.
- ``cursor``  — Cursor (`cursor-agent` CLI if present, else the `cursor-sdk`
  Python package); optional, only if available.
- ``manual``  — no auto-edit; prep the worktree + evidence and stop (a human or
  a separate step writes the diff). Also the safe default for tests.

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

    def to_log(self, prompt: str) -> dict:
        return {
            "backend": self.backend,
            "ok": self.ok,
            "summary": self.summary,
            "session_id": self.session_id,
            "error": self.error,
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
    "claude": ClaudeCoder,
    "cursor": CursorCoder,
    "manual": ManualCoder,
}


def get_coder(name: str = "auto") -> CoderBackend:
    """Resolve a coder backend by name; 'auto' prefers claude, then cursor, else manual."""
    if name != "auto":
        if name not in _BACKENDS:
            raise ValueError(
                f"Unknown coder backend: {name}. Choices: {sorted(_BACKENDS) + ['auto']}"
            )
        return _BACKENDS[name]()
    for candidate in ("claude", "cursor"):
        backend = _BACKENDS[candidate]()
        if backend.available():
            return backend
    return ManualCoder()
