"""Precise allowlist of harness files the auto-proposer may edit.

Derived directly from ``docs/grounded-intelligence-northstar.md`` (Green Lines /
Red lines). The auto-coder may ONLY touch the handful of *agent-behaviour*
surfaces below. This deliberately shrinks the proposer's search space (huge
signal for a hand-crafted agent) and hard-enforces the take-home constraint:
never touch tasks, backend state, tool behaviour, the scorer, the user
simulator, or the domain policy.

Green Lines that affect *agent accuracy* (from the northstar table):
- ``src/tau2/agent/llm_agent.py``          — ★ primary prompt + agent logic
- New agent module under ``src/tau2/agent/`` + register in ``src/tau2/registry.py``
- ``src/tau2/utils/llm_utils.py``          — LLM call wrapper (retries, arg repair)
- ``src/tau2/orchestrator/orchestrator.py``— agent-side recovery (fairness-sensitive)

Deliberately EXCLUDED even though the northstar lists them, because they are
tooling/experiment surfaces that do not change agent behaviour and would only
enlarge the search space: ``src/tau2/runner/``, ``scripts/``,
``src/tau2/scripts/``, ``src/experiments/``.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Exact files the proposer may EDIT (repo-root-relative POSIX paths).
ALLOWED_FILES: frozenset[str] = frozenset(
    {
        "src/tau2/agent/llm_agent.py",
        "src/tau2/registry.py",
        "src/tau2/utils/llm_utils.py",
        "src/tau2/orchestrator/orchestrator.py",
    }
)

# The proposer may CREATE new agent modules here (custom agents green line).
ALLOWED_NEW_DIRS: tuple[str, ...] = ("src/tau2/agent/",)

# Hard denylist (northstar "Red lines"). Redundant with the allowlist but kept
# for defense-in-depth and clear error messages.
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "data/tau2/domains/",  # tasks.json, db.json, policy.md, ...
    "src/tau2/domains/",  # tool behaviour (retail/tools.py)
    "src/tau2/evaluator/",  # scoring logic
    "src/tau2/user/",  # user simulator
)


def normalize(path: str) -> str:
    """Repo-root-relative POSIX form (strips leading ./ and whitespace)."""
    return PurePosixPath(path.strip().lstrip("./")).as_posix()


def is_allowed(path: str) -> bool:
    p = normalize(path)
    if any(p == pref.rstrip("/") or p.startswith(pref) for pref in FORBIDDEN_PREFIXES):
        return False
    if p in ALLOWED_FILES:
        return True
    # A NEW agent module: a .py file directly under src/tau2/agent/ (no nesting,
    # not a dunder like __init__.py).
    for d in ALLOWED_NEW_DIRS:
        if p.startswith(d) and p.endswith(".py"):
            rest = p[len(d) :]
            if "/" not in rest and not rest.startswith("__"):
                return True
    return False


def assert_allowed(paths: list[str]) -> None:
    bad = [p for p in paths if not is_allowed(p)]
    if bad:
        raise PermissionError(
            "Proposer attempted to edit files outside the harness allowlist: "
            + ", ".join(sorted(bad))
            + ". Allowed: "
            + ", ".join(sorted(ALLOWED_FILES))
            + " (plus a new *.py agent module under src/tau2/agent/)."
        )


def allowlist_for_prompt() -> str:
    lines = ["You may edit ONLY these files. Any other path is rejected outright:"]
    lines += [f"  - {f}" for f in sorted(ALLOWED_FILES)]
    lines.append(
        "  - a NEW *.py agent module directly under src/tau2/agent/ "
        "(and register it in src/tau2/registry.py)"
    )
    lines.append(
        "NEVER touch: data/tau2/domains/** (tasks.json, db.json, policy.md), "
        "src/tau2/domains/retail/tools.py, src/tau2/evaluator/**, src/tau2/user/**."
    )
    return "\n".join(lines)
