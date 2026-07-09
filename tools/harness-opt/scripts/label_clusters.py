"""Per-cluster labels + a concise LLM summary (mockable).

Produces `cluster_labels.json` (ClusterLabel per cluster). The key field is
`summary`: a 1-2 sentence, plain-English description of the cluster's shared
root cause, meant to be read at a glance (replaces deterministic gloss text).

Approach: we don't send full transcripts. For each cluster we aggregate the
structured signals over *all* members (dominant mechanism, top DB-diff
signatures, failed NL assertions, common tool chains, escalation rate) plus a
few deduped representative final agent messages, then make one small LLM call.
The aggregates make the summary faithful to the whole cluster; the message
samples give it texture. `--mock` yields a deterministic summary (tests/no-API).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import (
    Cluster,
    ClusterLabel,
    ClusterLabelsArtifact,
    ClustersArtifact,
    FeaturesArtifact,
    SimulationFeatures,
)
from lib.io import read_json_artifact, write_json_artifact
from lib.paths import artifact_path

# Cluster summaries are cheap tooling: one small structured call per cluster on a
# low-cost model. Keep this on a cheap tier — the summary content is short and
# the input is aggregated signals, not full transcripts, so a mini model suffices.
SUMMARY_MODEL = "gpt-4.1-mini"

# Plain-English gloss of each root-cause mechanism (for the mock summary and to
# prime the LLM). Kept in sync with trace_parser.classify_mechanism.
MECHANISM_PHRASE = {
    "bailed_transfer": "the agent escalated to a human instead of completing the task",
    "wrong_params": "the agent performed the action but with wrong values",
    "incomplete_multitask": "the agent completed only part of the required changes",
    "stalled_no_action": "the agent never executed the required change",
    "identification_failure": "the agent could not identify the user or order",
    "comm_miss": "the database was correct but the agent omitted required information",
    "premature_termination": "the run ended abnormally (max steps / too many errors)",
    "other": "an uncategorized failure",
}
MECHANISM_BLAME = {
    "bailed_transfer": ["escalation_gap"],
    "wrong_params": ["wrong_parameters"],
    "incomplete_multitask": ["incomplete_actions"],
    "stalled_no_action": ["no_action_taken"],
    "identification_failure": ["identification_gap"],
    "comm_miss": ["communication_gap"],
    "premature_termination": ["premature_termination"],
    "other": ["harness_gap"],
}


def build_cluster_context(
    members: list[SimulationFeatures],
    *,
    k_messages: int = 4,
) -> dict:
    """Aggregate structured signals over all members + sample a few messages."""
    n = len(members)
    mech = Counter(m.mechanism_class for m in members)
    ftypes = Counter(m.failure_type.value for m in members)
    db_sigs = Counter(m.db_diff_signature for m in members if m.db_diff_signature)
    nl_sigs = Counter(
        a for m in members for a in (m.nl_failed_assertions or [])
    )
    chains = Counter(
        "->".join(m.normalized_tool_chain) for m in members if m.normalized_tool_chain
    )

    messages: list[str] = []
    seen: set[str] = set()
    for m in members:
        text = (m.last_agent_message or "").strip()
        if text and text not in seen:
            seen.add(text)
            messages.append(text)
        if len(messages) >= k_messages:
            break

    return {
        "size": n,
        "num_tasks": len({m.task_id for m in members}),
        "mechanism": mech.most_common(1)[0][0] if mech else "other",
        "mechanism_dist": dict(mech),
        "failure_type_dist": dict(ftypes),
        "escalated": sum(1 for m in members if m.escalated_to_human),
        "top_db_signatures": db_sigs.most_common(3),
        "top_nl_assertions": nl_sigs.most_common(2),
        "top_tool_chains": chains.most_common(3),
        "sample_messages": messages,
    }


def _blame_tags(ctx: dict) -> list[str]:
    tags = list(MECHANISM_BLAME.get(ctx["mechanism"], ["harness_gap"]))
    kinds: set[str] = set()
    for sig, _ in ctx["top_db_signatures"]:
        for part in sig.split(";"):
            if ":" in part:
                kinds.add(part.split(":", 1)[0])
    if "missed" in kinds:
        tags.append("db_missing_write")
    if "wrong" in kinds:
        tags.append("db_wrong_write")
    if "extra" in kinds:
        tags.append("db_extra_write")
    if ctx["top_nl_assertions"]:
        tags.append("nl_assertion_gap")
    return list(dict.fromkeys(tags))  # dedupe, keep order


def _cohesion(ctx: dict) -> float:
    """1-5, from mechanism purity (fraction sharing the dominant mechanism)."""
    n = ctx["size"] or 1
    top = max(ctx["mechanism_dist"].values()) if ctx["mechanism_dist"] else n
    return round(1 + 4 * (top / n), 1)


def _context_text(cluster: Cluster, ctx: dict) -> str:
    lines = [
        f"size: {ctx['size']} sims across {ctx['num_tasks']} task(s)",
        f"dominant mechanism: {ctx['mechanism']} "
        f"({MECHANISM_PHRASE.get(ctx['mechanism'], '')})",
        f"mechanism distribution: {ctx['mechanism_dist']}",
        f"reward-basis mix: {ctx['failure_type_dist']}",
        f"escalated to human: {ctx['escalated']}/{ctx['size']}",
    ]
    if ctx["top_db_signatures"]:
        lines.append(
            "top DB divergences: "
            + "; ".join(f"{s} (x{c})" for s, c in ctx["top_db_signatures"])
        )
    if ctx["top_nl_assertions"]:
        lines.append(
            "failed NL assertions: "
            + "; ".join(f'"{s}" (x{c})' for s, c in ctx["top_nl_assertions"])
        )
    if ctx["top_tool_chains"]:
        lines.append(
            "common tool chains: "
            + " | ".join(s for s, _ in ctx["top_tool_chains"])
        )
    if ctx["sample_messages"]:
        lines.append(
            "sample final agent messages: "
            + " || ".join(ctx["sample_messages"])
        )
    return "\n".join(lines)


def _condense_db_sig(sig: str) -> str:
    """'missed:orders.*.status;missed:orders.*.exchange_items' -> 'missed status, exchange_items'."""
    by_kind: dict[str, list[str]] = {}
    for part in sig.split(";"):
        if ":" not in part:
            continue
        kind, path = part.split(":", 1)
        segs = [s for s in path.replace("[]", "").split(".") if s and s != "*"]
        leaf = segs[-1] if segs else path
        by_kind.setdefault(kind, [])
        if leaf not in by_kind[kind]:
            by_kind[kind].append(leaf)
    return "; ".join(f"{kind} {', '.join(leaves[:4])}" for kind, leaves in by_kind.items())


def _sentence(text: str) -> str:
    text = text.strip().rstrip(".")
    return (text[:1].upper() + text[1:]) if text else text


def _assemble_summary(root_cause: str, consequence: str) -> str:
    """Fixed schema so every cluster summary reads identically:

        "<root_cause>. <consequence>."

    Two descriptive clauses only — no count, no mechanism prefix.
    """
    parts = [_sentence(root_cause)]
    consequence = _sentence(consequence)
    if consequence:
        parts.append(consequence)
    return ". ".join(p for p in parts if p) + "."


def _mock_consequence(ctx: dict) -> str:
    if ctx["top_db_signatures"]:
        return f"DB gap: {_condense_db_sig(ctx['top_db_signatures'][0][0])}"
    if ctx["top_nl_assertions"]:
        return f'missing info, e.g. "{ctx["top_nl_assertions"][0][0]}"'
    return ""


def _mock_label(cluster: Cluster, ctx: dict, rep_ids: list[str]) -> ClusterLabel:
    root_cause = MECHANISM_PHRASE.get(ctx["mechanism"], "an uncategorized failure")
    return ClusterLabel(
        cluster_id=cluster.id,
        display_name=f"{ctx['mechanism']} ({ctx['size']})",
        cohesion=_cohesion(ctx),
        blame_tags=_blame_tags(ctx),
        summary=_assemble_summary(root_cause, _mock_consequence(ctx)),
        representative_simulation_ids=rep_ids,
    )


def _llm_label(
    cluster: Cluster,
    ctx: dict,
    rep_ids: list[str],
    model: str,
) -> ClusterLabel:
    from tau2.utils.llm_utils import generate, to_tau2_messages

    # The LLM fills ONLY the two descriptive clauses; we assemble the summary
    # deterministically so every cluster's summary has an identical structure.
    prompt = (
        "Summarize a failure cluster from a retail customer-service agent "
        "benchmark. Clusters group traces by shared root-cause mechanism.\n\n"
        f"Cluster {cluster.id} ({cluster.name}):\n"
        f"{_context_text(cluster, ctx)}\n\n"
        "Return JSON ONLY with EXACTLY these keys (no extra keys, no prose):\n"
        '  "root_cause": what the agent did wrong, ONE clause, <=14 words, '
        "lowercase, no counts / ids / trailing period.\n"
        '  "consequence": the resulting DB or communication error, ONE clause, '
        "<=12 words, lowercase, no trailing period.\n"
        '  "display_name": <=6 words.\n'
        '  "cohesion": integer 1-5 (5 = one crisp mechanism).\n'
        '  "blame_tags": list of short snake_case tags.\n'
    )
    messages = to_tau2_messages(
        [
            {
                "role": "system",
                "content": (
                    "You summarize agent failure clusters into a fixed schema. "
                    "Terse, lowercase clauses, JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ]
    )
    resp = generate(model=model, messages=messages, call_name="cluster_label")
    content = resp.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}") + 1
        data = json.loads(content[start:end]) if start >= 0 else {}

    root_cause = (data.get("root_cause") or "").strip() or MECHANISM_PHRASE.get(
        ctx["mechanism"], "an uncategorized failure"
    )
    consequence = (data.get("consequence") or "").strip() or _mock_consequence(ctx)
    return ClusterLabel(
        cluster_id=cluster.id,
        display_name=data.get("display_name") or f"{ctx['mechanism']} ({ctx['size']})",
        cohesion=float(data.get("cohesion", _cohesion(ctx))),
        blame_tags=list(data.get("blame_tags") or _blame_tags(ctx)),
        summary=_assemble_summary(root_cause, consequence),
        representative_simulation_ids=rep_ids,
    )


def run_label(
    run_name: str,
    *,
    mock: bool = False,
    model: str = SUMMARY_MODEL,
    overwrite: bool = False,
) -> None:
    clusters = read_json_artifact(
        artifact_path(run_name, "clusters.json"), ClustersArtifact
    )
    features = read_json_artifact(
        artifact_path(run_name, "features.json"), FeaturesArtifact
    )
    by_id = {s.simulation_id: s for s in features.simulations}

    labels: list[ClusterLabel] = []
    for cluster in clusters.clusters:
        members = [by_id[sid] for sid in cluster.simulation_ids if sid in by_id]
        rep_ids = cluster.simulation_ids[:5]
        if not members:
            labels.append(
                ClusterLabel(
                    cluster_id=cluster.id,
                    display_name=cluster.name[:80],
                    cohesion=3.0,
                    blame_tags=["harness_gap"],
                    summary=cluster.name,
                    representative_simulation_ids=rep_ids,
                )
            )
            continue
        ctx = build_cluster_context(members)
        if mock:
            labels.append(_mock_label(cluster, ctx, rep_ids))
        else:
            labels.append(_llm_label(cluster, ctx, rep_ids, model))

    artifact = ClusterLabelsArtifact(
        run_name=run_name,
        model=None if mock else model,
        labels=labels,
    )
    write_json_artifact(run_name, "cluster_labels.json", artifact, overwrite=overwrite)


def main() -> None:
    parser = argparse.ArgumentParser(description="Label clusters via LLM (or mock)")
    parser.add_argument("--run", required=True)
    parser.add_argument("--mock", action="store_true", help="Skip LLM calls")
    parser.add_argument(
        "--model", default=SUMMARY_MODEL, help="cheap model for cluster summaries"
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_label(args.run, mock=args.mock, model=args.model, overwrite=args.overwrite)
    print(f"Wrote cluster_labels.json for run {args.run}")


if __name__ == "__main__":
    main()
