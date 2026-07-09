"""Diversity-aware sampling of representative sims within a cluster.

A cluster already shares a mechanism signature, so members are similar — but they
still vary by task, tool chain, and policy-flag pattern. To give the proposer the
*range* of a failure mode (not N near-duplicate trials of one task), we pick sims
that maximize coverage: distinct tasks first, then distinct tool chains, then fill.
"""

from __future__ import annotations

from contracts.models import SimulationFeatures


def _chain_key(f: SimulationFeatures) -> tuple[str, ...]:
    return tuple(f.write_tool_sequence or f.normalized_tool_chain)


def _flags_key(f: SimulationFeatures) -> frozenset[str]:
    pf = f.policy_flags
    active = []
    if pf.auth_before_mutate is False:
        active.append("auth_missing")
    if pf.confirm_before_write is False:
        active.append("confirm_missing")
    if not pf.single_tool_per_turn:
        active.append("multi_tool")
    return frozenset(active)


def select_diverse(
    features: list[SimulationFeatures], n: int
) -> list[SimulationFeatures]:
    """Pick up to n sims maximizing coverage of distinct (task, chain, flags)."""
    if n <= 0 or not features:
        return []

    selected: list[SimulationFeatures] = []
    chosen: set[str] = set()
    seen_tasks: set[str] = set()
    seen_chains: set[tuple[str, ...]] = set()
    seen_flags: set[frozenset[str]] = set()

    def add(f: SimulationFeatures) -> None:
        selected.append(f)
        chosen.add(f.simulation_id)
        seen_tasks.add(f.task_id)
        seen_chains.add(_chain_key(f))
        seen_flags.add(_flags_key(f))

    # Pass 1: one per distinct task (avoid multiple trials of the same task).
    for f in features:
        if len(selected) >= n:
            return selected
        if f.task_id not in seen_tasks:
            add(f)

    # Pass 2: distinct tool chains not yet represented.
    for f in features:
        if len(selected) >= n:
            return selected
        if f.simulation_id in chosen:
            continue
        if _chain_key(f) not in seen_chains:
            add(f)

    # Pass 3: distinct flag patterns not yet represented.
    for f in features:
        if len(selected) >= n:
            return selected
        if f.simulation_id in chosen:
            continue
        if _flags_key(f) not in seen_flags:
            add(f)

    # Pass 4: fill remaining slots with anything left.
    for f in features:
        if len(selected) >= n:
            return selected
        if f.simulation_id not in chosen:
            add(f)

    return selected
