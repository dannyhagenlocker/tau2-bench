"""v2 dashboard: generate a self-contained static HTML trace viewer.

Reads Phase 0 artifacts (`features.json`, `clusters.json`, `cluster_labels.json`,
`manifest.json`) plus raw trajectories and emits `reports/<run>/trace_viewer.html`
— a single file with the data inlined and a vanilla-JS SPA that provides:

- a cluster browser grouped by failure taxonomy,
- an at-a-glance SVG swimlane per trace,
- a unified explorer where a second trace can be pinned for comparison, and
- a synchronized, semantically-aligned diff (LCS over normalized steps).

No server and no network: the trace data is embedded and all interaction is
client-side. Regenerate by re-running `analyze` (or `viewer`).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import (  # noqa: E402
    ClusterLabelsArtifact,
    ClustersArtifact,
    FeaturesArtifact,
    ManifestArtifact,
    SimulationFeatures,
)
from lib.io import read_json_artifact  # noqa: E402
from lib.paths import REPO_ROOT, artifact_path  # noqa: E402

from tau2.data_model.simulation import Results  # noqa: E402

TEMPLATE = Path(__file__).parent / "template.html"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_name_map(messages: list) -> dict[str, str]:
    """Map tool_call id -> tool name so tool results can be labeled."""
    names: dict[str, str] = {}
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            names[tc.id] = tc.name
    return names


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts) if ts else None
    except (ValueError, TypeError):
        return None


def _snippet(text: Optional[str], n: int = 60) -> str:
    text = (text or "").strip().replace("\n", " ")
    return (text[:n] + "…") if len(text) > n else text


def _add_timing(nodes: list[dict[str, Any]]) -> float:
    """Attach gap-before durations + offsets (seconds); return total span.

    Each node's bar spans [prev_ts, this_ts] — the elapsed producing this event
    (assistant node ≈ LLM latency; tool results ≈ instant for the local DB).
    """
    times = [_parse_ts(n.get("ts")) for n in nodes]
    first = next((t for t in times if t), None)
    if first is None:
        for n in nodes:
            n["start"] = 0.0
            n["dur"] = 0.0
        return 0.0
    last = prev = first
    for n, t in zip(nodes, times):
        cur = t or prev
        n["start"] = round(max((prev - first).total_seconds(), 0.0), 3)
        n["dur"] = round(max((cur - prev).total_seconds(), 0.0), 3)
        prev = cur
        last = max(last, cur)
    return round((last - first).total_seconds(), 3)


def _steps_for_sim(sim) -> tuple[list[dict[str, Any]], float]:
    """Build an ordered node tree (depth + timing) for the waterfall + diff.

    Nodes: user/assistant *turn* (depth 0), each tool call (depth 1), each tool
    result (depth 2). `key` is the value-free alignment token used by the diff.
    Returns (nodes, total_duration_seconds).
    """
    messages = sim.get_messages()
    id_to_name = _tool_name_map(messages)
    nodes: list[dict[str, Any]] = []
    idx = 0

    def add(**kw: Any) -> None:
        nonlocal idx
        kw["i"] = idx
        nodes.append(kw)
        idx += 1

    for msg in messages:
        role = getattr(msg, "role", "system")
        content = getattr(msg, "content", None)
        tool_calls = getattr(msg, "tool_calls", None)
        ts = getattr(msg, "timestamp", None)
        cost = getattr(msg, "cost", None)

        if role == "tool":
            name = id_to_name.get(getattr(msg, "id", None), "tool")
            error = bool(getattr(msg, "error", False))
            add(
                depth=2,
                lane="tool",
                kind="tool_result",
                label=name + (" ⚠" if error else ""),
                key=f"R:{name}" + (":e" if error else ""),
                content=content or "",
                tool=name,
                error=error,
                requestor=getattr(msg, "requestor", "assistant"),
                ts=ts,
                cost=None,
            )
            continue

        lane = (
            "user"
            if role == "user"
            else "assistant"
            if role == "assistant"
            else "system"
        )
        add(
            depth=0,
            lane=lane,
            kind="turn",
            label=_snippet(content) or (lane + " turn"),
            key=("U:text" if lane == "user" else "A:text"),
            content=content or "",
            ts=ts,
            cost=cost,
        )
        for tc in tool_calls or []:
            try:
                args = json.dumps(tc.arguments, default=str, ensure_ascii=False)
            except (TypeError, ValueError):
                args = str(tc.arguments)
            add(
                depth=1,
                lane=lane,
                kind="tool_call",
                label=tc.name,
                key=f"C:{tc.name}",
                content=args,
                tool=tc.name,
                ts=ts,
                cost=None,
            )

    total = _add_timing(nodes)
    return nodes, total


def _flags(feat: SimulationFeatures) -> list[str]:
    pf = feat.policy_flags
    out: list[str] = []
    if pf.auth_before_mutate is False:
        out.append("auth_missing")
    if pf.confirm_before_write is False:
        out.append("confirm_missing")
    if not pf.single_tool_per_turn:
        out.append("multi_tool_turn")
    if pf.num_env_errors:
        out.append(f"env_errors={pf.num_env_errors}")
    return out


def build_payload(run: str) -> dict[str, Any]:
    manifest = read_json_artifact(artifact_path(run, "manifest.json"), ManifestArtifact)
    features = read_json_artifact(artifact_path(run, "features.json"), FeaturesArtifact)
    clusters = read_json_artifact(artifact_path(run, "clusters.json"), ClustersArtifact)
    l0 = read_json_artifact(artifact_path(run, "clusters_l0.json"), ClustersArtifact)

    labels_path = artifact_path(run, "cluster_labels.json")
    labels: Optional[ClusterLabelsArtifact] = (
        read_json_artifact(labels_path, ClusterLabelsArtifact)
        if labels_path.exists()
        else None
    )
    label_by_id = {lb.cluster_id: lb for lb in labels.labels} if labels else {}

    sim_path = Path(manifest.simulation_path)
    if not sim_path.is_absolute():
        sim_path = REPO_ROOT / manifest.simulation_path
    results = Results.load(str(sim_path))
    sims_by_id = {s.id: s for s in results.simulations}

    feats_by_id = {f.simulation_id: f for f in features.simulations}

    sims_payload: dict[str, Any] = {}
    for sid, feat in feats_by_id.items():
        sim = sims_by_id.get(sid)
        if sim is None:
            continue
        steps, total_dur = _steps_for_sim(sim)
        sims_payload[sid] = {
            "task_id": feat.task_id,
            "trial": feat.trial,
            "reward": feat.reward,
            "failure_type": feat.failure_type.value,
            "termination_reason": feat.termination_reason,
            "db_diff_signature": feat.db_diff_signature,
            "nl_failure_signature": feat.nl_failure_signature,
            "tool_chain": feat.normalized_tool_chain
            or [t.name for t in feat.tool_sequence],
            "flags": _flags(feat),
            "num_steps": feat.num_steps,
            "agent_cost": feat.agent_cost,
            "total_dur": total_dur,
            "steps": steps,
        }

    # Flaky tasks: same task with both a passing and a failing trial.
    by_task: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for sid, sp in sims_payload.items():
        by_task[sp["task_id"]].append((sid, sp["reward"]))
    flaky = []
    for task_id, entries in by_task.items():
        passed = [sid for sid, r in entries if r >= 0.999]
        failed = [sid for sid, r in entries if r < 0.999]
        if passed and failed:
            flaky.append(
                {
                    "task_id": task_id,
                    "pass_sim": passed[0],
                    "fail_sim": failed[0],
                    "n_trials": len(entries),
                }
            )
    flaky.sort(key=lambda x: str(x["task_id"]))

    clusters_payload = []
    for c in clusters.clusters:
        lb = label_by_id.get(c.id)
        clusters_payload.append(
            {
                "id": c.id,
                "name": c.name,
                "failure_type": c.failure_type,
                "signature": c.signature or "",
                "count": c.count,
                "label": lb.display_name if lb else c.name,
                "blame": lb.blame_tags if lb else [],
                "summary": lb.summary if lb else "",
                "sims": [s for s in c.simulation_ids if s in sims_payload],
            }
        )

    pass_rate = (
        sum(1 for f in features.simulations if f.reward >= 0.999)
        / len(features.simulations)
        if features.simulations
        else 0.0
    )

    return {
        "run": run,
        "generated_at": _utc_now(),
        "manifest": {
            "domain": manifest.domain,
            "num_simulations": manifest.num_simulations,
            "num_trials": manifest.num_trials,
            "agent_llm": manifest.agent_llm,
            "user_llm": manifest.user_llm,
            "baseline_run": manifest.baseline_run,
        },
        "pass_rate": pass_rate,
        "l0": [{"name": c.name, "count": c.count} for c in l0.clusters],
        "clusters": clusters_payload,
        "flaky": flaky,
        "sims": sims_payload,
    }


def run_viewer(run: str, *, overwrite: bool = False) -> Path:
    payload = build_payload(run)
    template = TEMPLATE.read_text()
    data_json = json.dumps(payload, ensure_ascii=False)
    html = template.replace("/*__PAYLOAD__*/null", data_json)

    out = artifact_path(run, "trace_viewer.html")
    if out.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {out}")
    out.write_text(html)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the v2 static trace viewer")
    parser.add_argument("--run", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    out = run_viewer(args.run, overwrite=args.overwrite)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
