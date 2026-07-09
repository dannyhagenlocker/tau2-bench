"""Regenerate the proposal + lineage discoverability artifacts.

Called at the end of every propose / accept / reject so the artifact view and
the git-native view stay in sync:

- ``reports/<run>/proposals/{index.json, README.md}`` — per-run proposal table.
- ``reports/lineages/{index.json, README.md}`` — repo-level catalog of rollout
  branches (the "look through the different branches" entry point).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from contracts.models import (
    LineageArtifact,
    LineageIndexArtifact,
    ProposalMetadataArtifact,
)
from lib.io import read_json_artifact
from lib.paths import lineages_dir, proposals_dir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_proposals(run_name: str) -> list[ProposalMetadataArtifact]:
    root = proposals_dir(run_name)
    out: list[ProposalMetadataArtifact] = []
    if not root.exists():
        return out
    for meta_path in sorted(root.glob("*/metadata.json")):
        try:
            out.append(read_json_artifact(meta_path, ProposalMetadataArtifact))
        except Exception:
            continue
    return out


def rewrite_run_index(run_name: str) -> None:
    proposals = _load_proposals(run_name)
    proposals.sort(key=lambda p: p.created_at, reverse=True)

    index = {
        "contract_version": "1.0",
        "run_name": run_name,
        "generated_at": _now(),
        "proposals": [
            {
                "proposal_id": p.proposal_id,
                "cluster_id": p.cluster_id,
                "lineage_id": p.lineage_id,
                "status": p.status,
                "eval_verdict": p.eval_verdict,
                "proposal_branch": p.branch_name,
                "parent_commit": p.parent_commit,
                "resulting_commit": p.resulting_commit,
                "generation": p.generation,
                "coder_backend": p.coder_backend,
                "example_task_ids": p.example_task_ids,
                "diff_stat": p.diff_stat,
                "created_at": p.created_at,
                "one_line_summary": (p.failure_mode_summary or "").splitlines()[0][:160]
                if p.failure_mode_summary
                else "",
            }
            for p in proposals
        ],
    }
    root = proposals_dir(run_name)
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.json").write_text(json.dumps(index, indent=2))

    lines = [
        f"# Proposals — {run_name}",
        "",
        f"_Generated {index['generated_at']}. {len(proposals)} proposal(s)._",
        "",
        "| Proposal | Cluster | Lineage | Status | Verdict | Diff | Summary |",
        "|----------|---------|---------|--------|---------|------|---------|",
    ]
    for p in proposals:
        summary = (
            (p.failure_mode_summary or "").splitlines()[0][:80]
            if p.failure_mode_summary
            else ""
        )
        lines.append(
            f"| [`{p.proposal_id}`]({p.proposal_id}/) | {p.cluster_id} | "
            f"{p.lineage_id or '-'} | {p.status} | {p.eval_verdict or '-'} | "
            f"{p.diff_stat or '-'} | {summary} |"
        )
    (root / "README.md").write_text("\n".join(lines) + "\n")


def _load_lineages() -> list[LineageArtifact]:
    root = lineages_dir()
    out: list[LineageArtifact] = []
    if not root.exists():
        return out
    for path in sorted(root.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            out.append(read_json_artifact(path, LineageArtifact))
        except Exception:
            continue
    return out


def rewrite_lineages_index() -> None:
    lineages = _load_lineages()
    lineages.sort(key=lambda x: x.created_at)
    artifact = LineageIndexArtifact(lineages=lineages)
    root = lineages_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.json").write_text(artifact.model_dump_json(indent=2))

    lines = [
        "# Lineages (improvement-loop rollouts)",
        "",
        f"_Generated {_now()}. {len(lineages)} lineage(s)._",
        "",
        "Each lineage is a durable `lineage/<id>` git branch rooted at a base "
        "commit, accumulating one squashed commit per accepted proposal. Browse "
        "with `git log --oneline lineage/<id>`.",
        "",
        "| Lineage | Branch | Base | Tip | Gen | Accepted |",
        "|---------|--------|------|-----|-----|----------|",
    ]
    for lin in lineages:
        accepted = ", ".join(p.cluster_id for p in lin.accepted_proposals) or "-"
        lines.append(
            f"| {lin.lineage_id} | `{lin.branch}` | `{lin.base_commit[:8]}` | "
            f"`{lin.tip_commit[:8]}` | {lin.generation} | {accepted} |"
        )
    (root / "README.md").write_text("\n".join(lines) + "\n")


def rewrite_all(run_name: str) -> None:
    rewrite_run_index(run_name)
    rewrite_lineages_index()
