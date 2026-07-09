"""Accept or reject a proposal, and list proposals/lineages.

- accept: squash the proposal branch into ONE commit on lineage/<id>, advance the
  lineage tip, record it, mark the proposal accepted.
- reject: delete the ephemeral proposal branch; the lineage is untouched.
- list: print the per-run proposal table and the lineage catalog.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Optional

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import ProposalMetadataArtifact  # noqa: E402
from lib import lineage as lin  # noqa: E402
from lib.io import read_json_artifact  # noqa: E402
from lib.paths import REPO_ROOT, proposal_dir, proposals_dir  # noqa: E402
from lib.proposals_index import rewrite_all  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_meta(run_name: str, proposal_id: str) -> ProposalMetadataArtifact:
    path = proposal_dir(run_name, proposal_id) / "metadata.json"
    if not path.exists():
        raise SystemExit(f"Proposal not found: {run_name}/{proposal_id}")
    return read_json_artifact(path, ProposalMetadataArtifact)


def _save_meta(run_name: str, meta: ProposalMetadataArtifact) -> None:
    path = proposal_dir(run_name, meta.proposal_id) / "metadata.json"
    path.write_text(meta.model_dump_json(indent=2))
    (proposal_dir(run_name, meta.proposal_id) / "proposal_status.json").write_text(
        json.dumps({"status": meta.status}, indent=2)
    )


def _squash_message(meta: ProposalMetadataArtifact) -> str:
    head = (meta.failure_mode_summary or meta.cluster_id).splitlines()[0][:70]
    body = [
        "",
        f"Proposal: {meta.proposal_id}",
        f"Cluster: {meta.cluster_id}",
        f"Lineage: {meta.lineage_id}",
    ]
    if meta.eval_verdict:
        body.append(f"Subset verdict: {meta.eval_verdict}")
    return f"accept({meta.cluster_id}): {head}\n" + "\n".join(body)


def run_accept(run_name: str, proposal_id: str) -> ProposalMetadataArtifact:
    meta = _load_meta(run_name, proposal_id)
    if meta.status == "accepted":
        return meta
    if meta.diff_stat in (None, "no changes"):
        raise SystemExit(
            f"Proposal {proposal_id} has no diff to accept (coder made no changes)."
        )
    lineage_id = meta.lineage_id or run_name
    worktree, state = lin.ensure_lineage(lineage_id)

    new_tip = lin.accept_proposal(
        worktree, lineage_id, proposal_id, _squash_message(meta)
    )
    lin.record_accepted(
        state,
        proposal_id,
        meta.cluster_id,
        new_tip,
        (meta.failure_mode_summary or "").splitlines()[0]
        if meta.failure_mode_summary
        else None,
    )

    meta.status = "accepted"
    meta.resulting_commit = new_tip
    _save_meta(run_name, meta)
    rewrite_all(run_name)
    return meta


def run_reject(run_name: str, proposal_id: str) -> ProposalMetadataArtifact:
    meta = _load_meta(run_name, proposal_id)
    lineage_id = meta.lineage_id or run_name
    worktree, _ = lin.ensure_lineage(lineage_id)
    lin.reject_proposal(worktree, lineage_id, proposal_id)
    meta.status = "rejected"
    _save_meta(run_name, meta)
    rewrite_all(run_name)
    return meta


def run_delete(run_name: str, proposal_id: str) -> None:
    """Fully remove a proposal: delete its ephemeral branch AND its artifacts.

    Unlike `reject` (which keeps the audit trail), delete is destructive — use it
    to discard a draft you don't want cluttering the run.
    """
    meta = _load_meta(run_name, proposal_id)
    lineage_id = meta.lineage_id or run_name
    worktree, _ = lin.ensure_lineage(lineage_id)
    lin.reject_proposal(worktree, lineage_id, proposal_id)  # drop branch, keep lineage
    shutil.rmtree(proposal_dir(run_name, proposal_id), ignore_errors=True)
    rewrite_all(run_name)


def run_list(run_name: Optional[str] = None) -> None:
    if run_name:
        rewrite_all(run_name)
        readme = proposals_dir(run_name) / "README.md"
        if readme.exists():
            print(readme.read_text())
    print("\n=== Lineage branches ===")
    out = subprocess.run(
        ["git", "branch", "--list", "lineage/*"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    print(out.stdout.strip() or "(none)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Accept/reject/list proposals")
    sub = parser.add_subparsers(dest="command", required=True)

    p_accept = sub.add_parser("accept")
    p_accept.add_argument("--run", required=True)
    p_accept.add_argument("--proposal", required=True)

    p_reject = sub.add_parser("reject")
    p_reject.add_argument("--run", required=True)
    p_reject.add_argument("--proposal", required=True)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("--run", required=True)
    p_delete.add_argument("--proposal", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--run")

    args = parser.parse_args()
    if args.command == "accept":
        meta = run_accept(args.run, args.proposal)
        print(
            f"Accepted {meta.proposal_id} → {meta.lineage_id} @ {(meta.resulting_commit or '')[:12]}"
        )
    elif args.command == "reject":
        meta = run_reject(args.run, args.proposal)
        print(f"Rejected {meta.proposal_id}")
    elif args.command == "delete":
        run_delete(args.run, args.proposal)
        print(f"Deleted {args.proposal}")
    elif args.command == "list":
        run_list(args.run)


if __name__ == "__main__":
    main()
