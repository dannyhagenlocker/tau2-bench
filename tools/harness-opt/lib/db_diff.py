"""P1: structured DB diff signature via offline environment replay.

The live evaluator only stores a boolean ``db_match`` (a hash comparison).
To cluster DB failures by *mechanism* we need to know *what* diverged. We
reconstruct three DB states offline for each failing simulation:

- ``initial``   — env after task init, before any agent/gold actions
- ``gold``      — initial + the task's reference (golden) actions replayed
- ``predicted`` — initial + the agent's actual trajectory replayed

Diffing gold vs predicted (relative to initial) yields an abstracted,
value-free signature such as ``missed:orders.*.status;wrong:orders.*.payment_history[].amount``
that groups failures with the same root cause across tasks.
"""

from __future__ import annotations

import typing
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional

from tau2.data_model.simulation import SimulationRun
from tau2.data_model.tasks import Task

_MISSING = object()

_FIELD_NAMES: Optional[frozenset[str]] = None


def retail_field_names() -> frozenset[str]:
    """Schema field names for the retail DB (used to abstract record IDs to '*')."""
    global _FIELD_NAMES
    if _FIELD_NAMES is not None:
        return _FIELD_NAMES

    from pydantic import BaseModel

    from tau2.domains.retail import data_model as dm

    names: set[str] = set()
    seen: set = set()

    def iter_model_types(annotation: Any):
        args = typing.get_args(annotation)
        if not args:
            if isinstance(annotation, type):
                yield annotation
            return
        for a in args:
            yield from iter_model_types(a)

    def visit(model: Any) -> None:
        if model in seen:
            return
        seen.add(model)
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            return
        for fname, fld in model.model_fields.items():
            names.add(fname)
            for sub in iter_model_types(fld.annotation):
                visit(sub)

    visit(dm.RetailDB)
    _FIELD_NAMES = frozenset(names)
    return _FIELD_NAMES


@dataclass
class DbDiff:
    signature: str
    kinds: dict[str, int] = field(default_factory=dict)
    entities: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)


def _equal(a: Any, b: Any) -> bool:
    if a is _MISSING or b is _MISSING:
        return a is b
    return a == b


def _classify(initial: Any, gold: Any, predicted: Any) -> str:
    """Label a leaf divergence relative to the pre-action initial state."""
    p_eq_i = _equal(predicted, initial)
    g_eq_i = _equal(gold, initial)
    if p_eq_i and not g_eq_i:
        return "missed"  # agent failed to make a change the gold made
    if not p_eq_i and g_eq_i:
        return "extra"  # agent mutated something gold left untouched
    return "wrong"  # both diverged from initial, but differently


def _walk(path: tuple, initial: Any, gold: Any, predicted: Any, out: list) -> None:
    if gold is _MISSING or predicted is _MISSING:
        out.append((path, _classify(initial, gold, predicted)))
        return
    if _equal(gold, predicted):
        return
    if isinstance(gold, dict) and isinstance(predicted, dict):
        init_d = initial if isinstance(initial, dict) else {}
        for key in set(gold) | set(predicted):
            _walk(
                path + (key,),
                init_d.get(key, _MISSING),
                gold.get(key, _MISSING),
                predicted.get(key, _MISSING),
                out,
            )
    elif isinstance(gold, list) and isinstance(predicted, list):
        init_l = initial if isinstance(initial, list) else []
        for idx in range(max(len(gold), len(predicted))):
            _walk(
                path + (idx,),
                init_l[idx] if idx < len(init_l) else _MISSING,
                gold[idx] if idx < len(gold) else _MISSING,
                predicted[idx] if idx < len(predicted) else _MISSING,
                out,
            )
    else:
        out.append((path, _classify(initial, gold, predicted)))


def _abstract(path: tuple) -> str:
    fields = retail_field_names()
    parts: list[str] = []
    for el in path:
        if isinstance(el, int):
            parts.append("[]")
        elif el in fields:
            parts.append(el)
        else:
            parts.append("*")
    return ".".join(parts).replace(".[]", "[]")


def diff_dbs(initial: dict, gold: dict, predicted: dict) -> DbDiff:
    leaves: list[tuple[tuple, str]] = []
    _walk((), initial, gold, predicted, leaves)

    kinds_by_pattern: dict[str, set[str]] = {}
    kind_counts: dict[str, int] = {}
    entities: set[str] = set()
    for cpath, kind in leaves:
        pattern = _abstract(cpath)
        kinds_by_pattern.setdefault(pattern, set()).add(kind)
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        if cpath:
            entities.add(str(cpath[0]))

    sig_items = sorted(
        f"{kind}:{pattern}" for pattern, ks in kinds_by_pattern.items() for kind in ks
    )
    signature = ";".join(sig_items) if sig_items else "no_db_diff"
    return DbDiff(
        signature=signature,
        kinds=kind_counts,
        entities=sorted(entities),
        patterns=sorted(kinds_by_pattern),
    )


def compute_db_diff(
    task: Task,
    simulation: SimulationRun,
    base_db: Any,
) -> Optional[DbDiff]:
    """Replay gold + agent trajectories on fresh retail envs and diff end states.

    Returns None when the task lacks reference actions or replay fails.
    """
    from loguru import logger

    from tau2.domains.retail.environment import get_environment

    ec = task.evaluation_criteria
    if ec is None or ec.actions is None:
        return None

    init = task.initial_state
    init_data = init.initialization_data if init else None
    init_actions = init.initialization_actions if init else None
    msg_history = init.message_history if (init and init.message_history) else []

    # Replaying trajectories emits verbose per-tool DEBUG logs; silence them.
    logger.disable("tau2.environment")
    try:
        pred_env = get_environment(db=deepcopy(base_db))
        pred_env.set_state(init_data, init_actions, list(simulation.get_messages()))
        predicted = pred_env.tools.db.model_dump()

        gold_env = get_environment(db=deepcopy(base_db))
        gold_env.set_state(init_data, init_actions, list(msg_history))
        initial = gold_env.tools.db.model_dump()
        for action in ec.actions or []:
            try:
                gold_env.make_tool_call(
                    tool_name=action.name,
                    requestor=action.requestor,
                    **action.arguments,
                )
            except Exception:
                pass
        gold = gold_env.tools.db.model_dump()
    except Exception:
        return None
    finally:
        logger.enable("tau2.environment")

    return diff_dbs(initial, gold, predicted)
