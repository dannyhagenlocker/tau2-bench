"""LLM labels for cluster representatives (mockable)."""

from __future__ import annotations

import argparse
import json

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import (
    ClusterLabel,
    ClusterLabelsArtifact,
    ClustersArtifact,
    FeaturesArtifact,
)
from lib.io import read_json_artifact, write_json_artifact
from lib.paths import artifact_path


def _pick_representatives(
    cluster_sims: list[str],
    features_by_id: dict,
    n: int = 3,
) -> list[str]:
    return cluster_sims[:n]


def _mock_label(cluster_id: str, name: str, rep_ids: list[str]) -> ClusterLabel:
    blame: list[str] = []
    if "auth_missing" in name or "auth" in name.lower():
        blame.append("auth_gap")
    if "confirm_missing" in name or "confirm" in name.lower():
        blame.append("confirm_gap")
    if "communicate" in name:
        blame.append("communicate_gap")
    if "nl_only" in name or "nl=" in name:
        blame.append("nl_assertion_gap")
    if "mixed" in name:
        blame.append("db_state_error")
        blame.append("nl_assertion_gap")
    if "db_only" in name or "db=" in name:
        blame.append("db_state_error")
    if "missed:" in name:
        blame.append("db_missing_write")
    if "wrong:" in name:
        blame.append("db_wrong_write")
    if "extra:" in name:
        blame.append("db_extra_write")
    if not blame:
        blame.append("harness_gap")

    return ClusterLabel(
        cluster_id=cluster_id,
        display_name=name.replace("|", " / ")[:80],
        cohesion=4.0,
        blame_tags=blame,
        summary=f"Cluster {cluster_id}: {name}. Representatives: {', '.join(rep_ids)}",
        representative_simulation_ids=rep_ids,
    )


def _llm_label(
    cluster_id: str,
    name: str,
    rep_features: list,
    model: str,
) -> ClusterLabel:
    from tau2.utils.llm_utils import generate

    snippets = []
    for f in rep_features:
        snippets.append(
            f"task={f.task_id} tools={[t.name for t in f.tool_sequence]} "
            f"flags={f.policy_flags.model_dump()} embedding={f.embedding_text}"
        )
    prompt = (
        "Label this failure cluster for a retail customer-service agent benchmark.\n"
        f"Cluster id: {cluster_id}\n"
        f"Mechanism name: {name}\n"
        f"Representative traces:\n" + "\n".join(snippets) + "\n"
        "Respond with JSON only: "
        '{"display_name": str, "cohesion": 1-5, "blame_tags": [str], "summary": str}'
    )
    messages = [
        {"role": "system", "content": "You label agent failure clusters. JSON only."},
        {"role": "user", "content": prompt},
    ]
    resp = generate(model=model, messages=messages, call_name="cluster_label")
    content = resp.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}") + 1
        data = json.loads(content[start:end]) if start >= 0 else {}

    return ClusterLabel(
        cluster_id=cluster_id,
        display_name=data.get("display_name", name),
        cohesion=float(data.get("cohesion", 3)),
        blame_tags=list(data.get("blame_tags", ["harness_gap"])),
        summary=data.get("summary", name),
        representative_simulation_ids=[f.simulation_id for f in rep_features],
    )


def run_label(
    run_name: str,
    *,
    mock: bool = False,
    model: str = "gpt-4.1-mini",
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
        rep_ids = _pick_representatives(cluster.simulation_ids, by_id)
        rep_features = [by_id[sid] for sid in rep_ids if sid in by_id]
        if mock or not rep_features:
            labels.append(_mock_label(cluster.id, cluster.name, rep_ids))
        else:
            labels.append(_llm_label(cluster.id, cluster.name, rep_features, model))

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
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_label(args.run, mock=args.mock, model=args.model, overwrite=args.overwrite)
    print(f"Wrote cluster_labels.json for run {args.run}")


if __name__ == "__main__":
    main()
